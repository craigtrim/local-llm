import asyncio
import json as json_mod
import logging
import random
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import ollama as ollama_lib

from local_llm.prompt import wrap_system_prompt
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import archive, assistants, client
from .config import (
    MAX_INPUT_CHARS,
    SUMMARIZE_PROMPT,
    SUMMARY_MODEL,
    SYSTEM_PROMPT,
    TITLE_PROMPT,
    TOKEN_ESTIMATE_RATIO,
)
from .history import ConversationHistory

log = logging.getLogger("local_llm.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = FastAPI(title="local-llm")

WEB_DIR = Path(__file__).resolve().parent / "web"


class SessionInfo(NamedTuple):
    model: str
    assistant_id: str | None
    assistant_name: str | None
    assistant_color: str | None
    assistant_uuid: str | None
    assistant_version: int | None
    history: ConversationHistory
    created_at: str = ""
    client_ip: str | None = None
    user_agent: str | None = None


sessions: dict[str, SessionInfo] = {}
# Mutable per-session state (source archive filename for overwrite)
session_meta: dict[str, dict] = {}


def _get_session(session_id: str) -> SessionInfo:
    if session_id not in sessions:
        log.warning("Session not found: %s", session_id)
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


def _init_meta(session_id: str, source_archive: str | None = None) -> None:
    session_meta[session_id] = {"source_archive": source_archive}


def _autosave(session_id: str) -> None:
    """Save current session to archive, overwriting source if resumed."""
    if session_id not in sessions:
        return
    info = sessions[session_id]
    meta = session_meta.get(session_id, {})
    overwrite = meta.get("source_archive")
    path = archive.save(
        info.history.messages, info.history.title,
        info.assistant_id, info.assistant_name,
        info.assistant_uuid, info.assistant_version,
        info.model, info.client_ip, info.user_agent, info.created_at,
        overwrite_path=overwrite,
    )
    # Capture filename on first save so subsequent saves overwrite
    if path and not overwrite:
        session_meta.setdefault(session_id, {})["source_archive"] = path.name


def _create_session(model: str, assistant_config: dict | None = None) -> tuple[str, ConversationHistory]:
    context_length = client.get_context_length(model)
    summary_model = SUMMARY_MODEL or model
    log.info("Creating session for model=%s context_length=%d", model, context_length)

    # Apply assistant overrides
    system_prompt = SYSTEM_PROMPT
    token_estimate_ratio = None
    context_reserve = None
    if assistant_config:
        system_prompt = assistant_config.get("system_prompt") or SYSTEM_PROMPT
        if assistant_config.get("context_tokens"):
            context_length = min(context_length, assistant_config["context_tokens"])
        token_estimate_ratio = assistant_config.get("token_estimate_ratio")
        context_reserve = assistant_config.get("context_reserve")

    # Wrap system prompt with behavioral guardrails (#57)
    wrap_enabled = assistant_config.get("wrap_system_prompt", True) if assistant_config else True
    system_prompt = wrap_system_prompt(system_prompt, enable=wrap_enabled)

    def summarize_fn(msgs: list[dict]) -> str:
        return client.summarize(msgs, summary_model, SUMMARIZE_PROMPT)

    def on_truncate(msgs: list[dict]) -> None:
        archive.save(msgs, model=model)

    def title_fn(msgs: list[dict]) -> str:
        return client.generate_title(msgs, summary_model, TITLE_PROMPT)

    a_uuid = assistant_config.get("uuid") if assistant_config else None
    a_name = assistant_config.get("name") if assistant_config else None

    history = ConversationHistory(
        context_limit=context_length,
        summarize_fn=summarize_fn,
        on_truncate=on_truncate,
        title_fn=title_fn,
        token_estimate_ratio=token_estimate_ratio,
        context_reserve=context_reserve,
        assistant_uuid=a_uuid,
        assistant_name=a_name,
    )
    if system_prompt:
        history.add("system", system_prompt)

    session_id = uuid.uuid4().hex[:12]
    log.info("Session created: %s", session_id)
    return session_id, history


# --- REST endpoints ---


@app.get("/api/models")
async def get_models() -> dict:
    log.info("GET /api/models")
    models = await asyncio.to_thread(client.list_models)
    log.info("Models found: %s", models)
    return {"models": models}


# --- Assistant endpoints ---


@app.get("/api/assistants")
async def get_assistants() -> dict:
    log.info("GET /api/assistants")
    result = await asyncio.to_thread(assistants.list_assistants)
    return {"assistants": result}


class SaveAssistantRequest(BaseModel):
    name: str
    model: str | None = None
    system_prompt: str
    description: str | None = None
    avatar_color: str | None = None
    context_tokens: int | None = None
    token_estimate_ratio: float | None = None
    context_reserve: int | None = None
    wrap_system_prompt: bool | None = None


@app.post("/api/assistants")
async def create_assistant(body: SaveAssistantRequest) -> dict:
    log.info("POST /api/assistants name=%s", body.name)
    config = body.model_dump(exclude_none=True)
    try:
        saved = await asyncio.to_thread(
            assistants.save_assistant, config,
            generate_greetings_fn=client.generate_greetings,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return saved


@app.put("/api/assistants/{assistant_id}")
async def update_assistant(assistant_id: str, body: SaveAssistantRequest) -> dict:
    log.info("PUT /api/assistants/%s", assistant_id)
    existing = await asyncio.to_thread(assistants.get_assistant, assistant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Assistant not found")
    config = body.model_dump(exclude_none=True)
    config["id"] = assistant_id
    try:
        saved = await asyncio.to_thread(
            assistants.save_assistant, config,
            generate_greetings_fn=client.generate_greetings,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return saved


@app.delete("/api/assistants/{assistant_id}")
async def delete_assistant_endpoint(assistant_id: str) -> dict:
    log.info("DELETE /api/assistants/%s", assistant_id)
    try:
        deleted = await asyncio.to_thread(assistants.delete_assistant, assistant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return {"deleted": assistant_id}


# --- Session endpoints ---


class CreateSessionRequest(BaseModel):
    model: str | None = None
    assistant_id: str | None = None


@app.post("/api/sessions")
async def create_session(body: CreateSessionRequest, request: Request) -> dict:
    log.info("POST /api/sessions model=%s assistant_id=%s", body.model, body.assistant_id)
    assistant_config = None
    assistant_id = None
    assistant_name = None
    assistant_color = None

    if body.assistant_id:
        assistant_config = await asyncio.to_thread(assistants.get_assistant, body.assistant_id)
        if not assistant_config:
            raise HTTPException(status_code=404, detail="Assistant not found")
        model = body.model or assistant_config.get("model")
        assistant_id = assistant_config["id"]
        assistant_name = assistant_config.get("name")
        assistant_color = assistant_config.get("avatar_color")
    else:
        model = body.model

    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    a_uuid = assistant_config.get("uuid") if assistant_config else None
    a_version = assistant_config.get("version") if assistant_config else None

    sid, history = await asyncio.to_thread(_create_session, model, assistant_config)
    now = datetime.now(timezone.utc).isoformat()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    sessions[sid] = SessionInfo(
        model=model,
        assistant_id=assistant_id,
        assistant_name=assistant_name,
        assistant_color=assistant_color,
        assistant_uuid=a_uuid,
        assistant_version=a_version,
        history=history,
        created_at=now,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    _init_meta(sid)
    ctx = await asyncio.to_thread(client.get_context_length, model)
    greeting = None
    if assistant_config:
        greetings = assistant_config.get("greetings", [])
        if greetings:
            greeting = random.choice(greetings)
    return {
        "session_id": sid,
        "model": model,
        "context_length": ctx,
        "assistant_id": assistant_id,
        "assistant_name": assistant_name,
        "assistant_color": assistant_color,
        "assistant_uuid": a_uuid,
        "greeting": greeting,
    }


@app.get("/api/sessions/{session_id}/status")
async def get_status(session_id: str) -> dict:
    log.info("GET /api/sessions/%s/status", session_id)
    info = _get_session(session_id)
    stats = info.history.stats()
    stats["model"] = info.model
    stats["assistant_id"] = info.assistant_id
    stats["assistant_name"] = info.assistant_name
    stats["created_at"] = info.created_at
    stats["client_ip"] = info.client_ip
    ratio = info.history.token_estimate_ratio
    dynamic_chars = int(stats["tokens_remaining"] * ratio)
    stats["max_input_chars"] = max(500, min(MAX_INPUT_CHARS, dynamic_chars))
    meta = session_meta.get(session_id, {})
    stats["source_archive"] = meta.get("source_archive")
    log.info("Status: %s", stats)
    return stats


@app.post("/api/sessions/{session_id}/clear")
async def clear_session(session_id: str) -> dict:
    log.info("POST /api/sessions/%s/clear", session_id)
    info = _get_session(session_id)
    # Auto-save already keeps the archive current; just clean up
    sessions.pop(session_id)
    session_meta.pop(session_id, None)

    # Reload assistant config to preserve it in the new session
    assistant_config = None
    if info.assistant_id:
        assistant_config = await asyncio.to_thread(assistants.get_assistant, info.assistant_id)

    now = datetime.now(timezone.utc).isoformat()
    new_sid, new_history = await asyncio.to_thread(_create_session, info.model, assistant_config)
    sessions[new_sid] = SessionInfo(
        model=info.model,
        assistant_id=info.assistant_id,
        assistant_name=info.assistant_name,
        assistant_color=info.assistant_color,
        assistant_uuid=info.assistant_uuid,
        assistant_version=info.assistant_version,
        history=new_history,
        created_at=now,
        client_ip=info.client_ip,
        user_agent=info.user_agent,
    )
    _init_meta(new_sid)
    greeting = None
    if assistant_config:
        greetings = assistant_config.get("greetings", [])
        if greetings:
            greeting = random.choice(greetings)
    log.info("Session cleared, new session: %s", new_sid)
    return {"session_id": new_sid, "model": info.model, "greeting": greeting}


@app.post("/api/sessions/{session_id}/compact")
async def compact_session(session_id: str) -> dict:
    """Trigger context compaction without clearing the session (#55)."""
    log.info("POST /api/sessions/%s/compact", session_id)
    info = _get_session(session_id)
    info.history.get_messages()  # trigger compaction if over budget
    await asyncio.to_thread(_autosave, session_id)
    stats = info.history.stats()
    stats["model"] = info.model
    stats["assistant_id"] = info.assistant_id
    stats["assistant_name"] = info.assistant_name
    stats["created_at"] = info.created_at
    stats["client_ip"] = info.client_ip
    ratio = info.history.token_estimate_ratio
    dynamic_chars = int(stats["tokens_remaining"] * ratio)
    stats["max_input_chars"] = max(500, min(MAX_INPUT_CHARS, dynamic_chars))
    meta = session_meta.get(session_id, {})
    stats["source_archive"] = meta.get("source_archive")
    log.info("Compact result: %s", stats)
    return stats



@app.post("/api/sessions/{session_id}/pop")
async def pop_last_response(session_id: str) -> dict:
    """Remove the last assistant message for regeneration (#20)."""
    log.info("POST /api/sessions/%s/pop", session_id)
    info = _get_session(session_id)
    removed = info.history.pop_last_assistant()
    if removed is None:
        raise HTTPException(status_code=409, detail="No assistant message to remove")
    await asyncio.to_thread(_autosave, session_id)
    return {"removed": True}


class FeedbackPayload(BaseModel):
    session_id: str
    rating: str
    message_content: str
    message_index: int


@app.post("/api/feedback")
async def submit_feedback(payload: FeedbackPayload) -> dict:
    """Save per-message thumbs up/down feedback (#20)."""
    log.info("POST /api/feedback session=%s rating=%s", payload.session_id, payload.rating)
    if payload.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    feedback_dir = Path(".user/feedback")
    feedback_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    filename = f"{payload.session_id}_{ts}_{payload.rating}.json"
    data: dict = {
        "session_id": payload.session_id,
        "rating": payload.rating,
        "message_index": payload.message_index,
        "message_content": payload.message_content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if payload.session_id in sessions:
        info = sessions[payload.session_id]
        data["model"] = info.model
        data["assistant_id"] = info.assistant_id
        data["assistant_name"] = info.assistant_name
    (feedback_dir / filename).write_text(json_mod.dumps(data, indent=2))
    return {"saved": True}


class RenameTitleRequest(BaseModel):
    title: str


@app.post("/api/sessions/{session_id}/title")
async def rename_title(session_id: str, body: RenameTitleRequest) -> dict:
    log.info("POST /api/sessions/%s/title -> %s", session_id, body.title)
    info = _get_session(session_id)
    info.history.set_title(body.title)
    return {"title": info.history.title}


@app.get("/api/archives")
async def get_archives() -> dict:
    log.info("GET /api/archives")
    archives = await asyncio.to_thread(archive.list_archives)
    log.info("Archives found: %d", len(archives))
    return {"archives": archives}


@app.delete("/api/archives/{filename}")
async def delete_archive(filename: str) -> dict:
    log.info("DELETE /api/archives/%s", filename)
    deleted = await asyncio.to_thread(archive.delete_archive, filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Archive not found")
    return {"deleted": filename}


class RenameArchiveRequest(BaseModel):
    title: str


@app.patch("/api/archives/{filename}")
async def rename_archive(filename: str, body: RenameArchiveRequest) -> dict:
    """Rename an archived conversation's title (#41)."""
    log.info("PATCH /api/archives/%s -> %s", filename, body.title)
    renamed = await asyncio.to_thread(archive.rename_archive, filename, body.title)
    if not renamed:
        raise HTTPException(status_code=404, detail="Archive not found")
    return {"filename": filename, "title": body.title}


@app.get("/api/archives/{filename}")
async def get_archive(filename: str) -> dict:
    log.info("GET /api/archives/%s", filename)
    data = await asyncio.to_thread(archive.load_archive, filename)
    if not data:
        raise HTTPException(status_code=404, detail="Archive not found")
    return {"messages": data.get("messages", [])}


class ResumeSessionRequest(BaseModel):
    model: str | None = None
    filename: str
    assistant_id: str | None = None


@app.post("/api/sessions/resume")
async def resume_session(body: ResumeSessionRequest, request: Request) -> dict:
    log.info("POST /api/sessions/resume filename=%s assistant_id=%s", body.filename, body.assistant_id)
    data = await asyncio.to_thread(archive.load_archive, body.filename)
    if not data:
        raise HTTPException(status_code=404, detail="Archive not found or invalid")

    messages = data.get("messages", [])
    assistant_config = None
    assistant_id = body.assistant_id or data.get("assistant_id")
    assistant_name = None
    assistant_color = None

    a_uuid = data.get("assistant_uuid")
    if assistant_id:
        assistant_config = await asyncio.to_thread(assistants.get_assistant, assistant_id)
        if assistant_config:
            assistant_name = assistant_config.get("name")
            assistant_color = assistant_config.get("avatar_color")
            a_uuid = a_uuid or assistant_config.get("uuid")

    a_version = assistant_config.get("version") if assistant_config else None
    model = body.model or (assistant_config and assistant_config.get("model"))
    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    sid, history = await asyncio.to_thread(_create_session, model, assistant_config)

    restored = 0
    for msg in messages:
        if msg["role"] == "system":
            continue
        history.add(msg["role"], msg["content"])
        restored += 1

    now = datetime.now(timezone.utc).isoformat()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    sessions[sid] = SessionInfo(
        model=model,
        assistant_id=assistant_id,
        assistant_name=assistant_name,
        assistant_color=assistant_color,
        assistant_uuid=a_uuid,
        assistant_version=a_version,
        history=history,
        created_at=now,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    _init_meta(sid, source_archive=body.filename)
    ctx = await asyncio.to_thread(client.get_context_length, model)
    log.info("Session resumed: %s with %d messages restored", sid, restored)
    return {
        "session_id": sid,
        "model": model,
        "context_length": ctx,
        "messages_restored": restored,
        "title": history.title,
        "assistant_id": assistant_id,
        "assistant_name": assistant_name,
        "assistant_color": assistant_color,
        "assistant_uuid": a_uuid,
    }


class ChangeModelRequest(BaseModel):
    model: str


@app.post("/api/sessions/{session_id}/model")
async def change_model(session_id: str, body: ChangeModelRequest, request: Request) -> dict:
    log.info("POST /api/sessions/%s/model -> %s", session_id, body.model)
    info = _get_session(session_id)
    sessions.pop(session_id)
    session_meta.pop(session_id, None)
    now = datetime.now(timezone.utc).isoformat()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    new_sid, new_history = await asyncio.to_thread(_create_session, body.model)
    sessions[new_sid] = SessionInfo(
        model=body.model,
        assistant_id=None,
        assistant_name=None,
        assistant_color=None,
        assistant_uuid=None,
        assistant_version=None,
        history=new_history,
        created_at=now,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    _init_meta(new_sid)
    ctx = await asyncio.to_thread(client.get_context_length, body.model)
    return {"session_id": new_sid, "model": body.model, "context_length": ctx}


class ChangeAssistantRequest(BaseModel):
    assistant_id: str
    model: str | None = None


@app.post("/api/sessions/{session_id}/assistant")
async def change_assistant(session_id: str, body: ChangeAssistantRequest, request: Request) -> dict:
    log.info("POST /api/sessions/%s/assistant -> %s", session_id, body.assistant_id)
    info = _get_session(session_id)
    sessions.pop(session_id)
    session_meta.pop(session_id, None)

    assistant_config = await asyncio.to_thread(assistants.get_assistant, body.assistant_id)
    if not assistant_config:
        raise HTTPException(status_code=404, detail="Assistant not found")

    model = body.model or assistant_config.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    now = datetime.now(timezone.utc).isoformat()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    new_sid, new_history = await asyncio.to_thread(_create_session, model, assistant_config)
    sessions[new_sid] = SessionInfo(
        model=model,
        assistant_id=assistant_config["id"],
        assistant_name=assistant_config.get("name"),
        assistant_color=assistant_config.get("avatar_color"),
        assistant_uuid=assistant_config.get("uuid"),
        assistant_version=assistant_config.get("version"),
        history=new_history,
        created_at=now,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    _init_meta(new_sid)
    ctx = await asyncio.to_thread(client.get_context_length, model)
    return {
        "session_id": new_sid,
        "model": model,
        "context_length": ctx,
        "assistant_id": assistant_config["id"],
        "assistant_name": assistant_config.get("name"),
        "assistant_color": assistant_config.get("avatar_color"),
    }


# --- WebSocket streaming chat ---


@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    log.info("WebSocket connect: session=%s", session_id)
    await ws.accept()
    log.info("WebSocket accepted: session=%s", session_id)

    if session_id not in sessions:
        log.error("WebSocket session not found: %s", session_id)
        await ws.send_json({"type": "error", "content": "Session not found"})
        await ws.close()
        return

    try:
        while True:
            user_text = await ws.receive_text()
            if user_text == "__STOP__":
                log.info("Ignoring stale stop signal")
                continue
            log.info("WebSocket received message: %s", user_text[:100])
            info = sessions[session_id]
            model = info.model
            history = info.history

            stats = history.stats()
            ratio = history.token_estimate_ratio
            dynamic_chars = int(stats["tokens_remaining"] * ratio)
            char_limit = min(MAX_INPUT_CHARS, dynamic_chars)
            if len(user_text) > char_limit:
                log.warning("Message too long: %d chars, limit %d", len(user_text), char_limit)
                await ws.send_json({
                    "type": "error",
                    "content": f"Message too long ({len(user_text):,} chars, limit {char_limit:,})",
                })
                continue

            history.add("user", user_text)
            await asyncio.to_thread(_autosave, session_id)
            messages = history.get_messages()
            log.info("Calling ollama.chat(model=%s, stream=True) with %d messages", model, len(messages))
            await ws.send_json({"type": "thinking", "content": ""})  # (#37)

            token_q: asyncio.Queue[str | None] = asyncio.Queue()
            error_holder: list[Exception] = []
            stop_event = threading.Event()
            loop = asyncio.get_running_loop()

            def stream_sync():
                try:
                    token_count = 0
                    for chunk in ollama_lib.chat(
                        model=model, messages=messages, stream=True
                    ):
                        if stop_event.is_set():
                            log.info("Stop signal received, breaking stream")
                            break
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            loop.call_soon_threadsafe(token_q.put_nowait, token)
                            token_count += 1
                    log.info("Streaming complete, %d tokens produced", token_count)
                except Exception as e:
                    log.error("Error in stream_sync: %s", e)
                    error_holder.append(e)
                finally:
                    loop.call_soon_threadsafe(token_q.put_nowait, None)

            full_response: list[str] = []
            stopped = False

            async def relay_tokens():
                while True:
                    token = await token_q.get()
                    if token is None:
                        break
                    full_response.append(token)
                    await ws.send_json({"type": "token", "content": token})

            async def listen_for_stop():
                nonlocal stopped
                try:
                    while True:
                        msg = await ws.receive_text()
                        if msg == "__STOP__":
                            log.info("Client sent stop signal")
                            stop_event.set()
                            stopped = True
                            # Push sentinel so relay_tokens exits
                            await token_q.put(None)
                            return
                except Exception:
                    pass

            executor_task = loop.run_in_executor(None, stream_sync)
            relay_task = asyncio.create_task(relay_tokens())
            stop_task = asyncio.create_task(listen_for_stop())

            await relay_task
            stop_task.cancel()
            try:
                await stop_task
            except asyncio.CancelledError:
                pass
            await executor_task

            if error_holder and not stopped:
                error_msg = str(error_holder[0])
                log.error("Sending error to client: %s", error_msg)
                await ws.send_json({"type": "error", "content": error_msg})
                continue

            complete_text = "".join(full_response)
            log.info(
                "Response %s, length=%d chars",
                "stopped" if stopped else "complete",
                len(complete_text),
            )

            if complete_text:
                history.add("assistant", complete_text)
                history.get_messages()  # trigger compaction if over budget (#55)
                await asyncio.to_thread(_autosave, session_id)

            if stopped:
                await ws.send_json({"type": "stopped", "content": complete_text})
            else:
                await ws.send_json({"type": "done", "content": complete_text})

            if history.title:
                await ws.send_json({"type": "title", "content": history.title})
    except WebSocketDisconnect:
        log.info("WebSocket disconnected: session=%s", session_id)
    except Exception as e:
        log.error("WebSocket error: %s", e, exc_info=True)
        try:
            await ws.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


# --- Static file serving ---


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def serve():
    import uvicorn

    uvicorn.run("local_llm.api:app", host="0.0.0.0", port=8000)
