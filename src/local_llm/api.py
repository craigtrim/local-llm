import asyncio
import logging
import queue
import uuid
from pathlib import Path

import ollama as ollama_lib
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import archive, client
from .config import SUMMARIZE_PROMPT, SUMMARY_MODEL, SYSTEM_PROMPT, TITLE_PROMPT
from .history import ConversationHistory

log = logging.getLogger("local_llm.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = FastAPI(title="local-llm")

WEB_DIR = Path(__file__).resolve().parent / "web"

sessions: dict[str, tuple[str, ConversationHistory]] = {}


def _get_session(session_id: str) -> tuple[str, ConversationHistory]:
    if session_id not in sessions:
        log.warning("Session not found: %s", session_id)
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


def _create_session(model: str) -> tuple[str, ConversationHistory]:
    context_length = client.get_context_length(model)
    summary_model = SUMMARY_MODEL or model
    log.info("Creating session for model=%s context_length=%d", model, context_length)

    def summarize_fn(msgs: list[dict]) -> str:
        return client.summarize(msgs, summary_model, SUMMARIZE_PROMPT)

    def on_truncate(msgs: list[dict]) -> None:
        archive.save(msgs)

    def title_fn(msgs: list[dict]) -> str:
        return client.generate_title(msgs, summary_model, TITLE_PROMPT)

    history = ConversationHistory(
        context_limit=context_length,
        summarize_fn=summarize_fn,
        on_truncate=on_truncate,
        title_fn=title_fn,
    )
    if SYSTEM_PROMPT:
        history.add("system", SYSTEM_PROMPT)

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


class CreateSessionRequest(BaseModel):
    model: str


@app.post("/api/sessions")
async def create_session(body: CreateSessionRequest) -> dict:
    log.info("POST /api/sessions model=%s", body.model)
    sid, history = await asyncio.to_thread(_create_session, body.model)
    sessions[sid] = (body.model, history)
    ctx = await asyncio.to_thread(client.get_context_length, body.model)
    return {"session_id": sid, "model": body.model, "context_length": ctx}


@app.get("/api/sessions/{session_id}/status")
async def get_status(session_id: str) -> dict:
    log.info("GET /api/sessions/%s/status", session_id)
    model, history = _get_session(session_id)
    stats = history.stats()
    stats["model"] = model
    log.info("Status: %s", stats)
    return stats


@app.post("/api/sessions/{session_id}/clear")
async def clear_session(session_id: str) -> dict:
    log.info("POST /api/sessions/%s/clear", session_id)
    model, history = _get_session(session_id)
    sessions.pop(session_id)
    await asyncio.to_thread(archive.save, history.messages)
    new_sid, new_history = await asyncio.to_thread(_create_session, model)
    sessions[new_sid] = (model, new_history)
    log.info("Session cleared, new session: %s", new_sid)
    return {"session_id": new_sid, "model": model}


class RenameTitleRequest(BaseModel):
    title: str


@app.post("/api/sessions/{session_id}/title")
async def rename_title(session_id: str, body: RenameTitleRequest) -> dict:
    log.info("POST /api/sessions/%s/title -> %s", session_id, body.title)
    _, history = _get_session(session_id)
    history.set_title(body.title)
    return {"title": history.title}


class ChangeModelRequest(BaseModel):
    model: str


@app.post("/api/sessions/{session_id}/model")
async def change_model(session_id: str, body: ChangeModelRequest) -> dict:
    log.info("POST /api/sessions/%s/model -> %s", session_id, body.model)
    _, old_history = _get_session(session_id)
    sessions.pop(session_id)
    await asyncio.to_thread(archive.save, old_history.messages)
    new_sid, new_history = await asyncio.to_thread(_create_session, body.model)
    sessions[new_sid] = (body.model, new_history)
    ctx = await asyncio.to_thread(client.get_context_length, body.model)
    return {"session_id": new_sid, "model": body.model, "context_length": ctx}


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
            log.info("WebSocket received message: %s", user_text[:100])
            model, history = sessions[session_id]

            history.add("user", user_text)
            messages = history.get_messages()
            log.info("Calling ollama.chat(model=%s, stream=True) with %d messages", model, len(messages))

            q: queue.Queue[str | None] = queue.Queue()
            error_holder: list[Exception] = []

            def stream_sync():
                try:
                    token_count = 0
                    for chunk in ollama_lib.chat(
                        model=model, messages=messages, stream=True
                    ):
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            q.put(token)
                            token_count += 1
                    log.info("Streaming complete, %d tokens produced", token_count)
                except Exception as e:
                    log.error("Error in stream_sync: %s", e)
                    error_holder.append(e)
                finally:
                    q.put(None)

            loop = asyncio.get_event_loop()
            task = loop.run_in_executor(None, stream_sync)

            full_response: list[str] = []
            while True:
                try:
                    token = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                if token is None:
                    break
                full_response.append(token)
                await ws.send_json({"type": "token", "content": token})

            await task

            if error_holder:
                error_msg = str(error_holder[0])
                log.error("Sending error to client: %s", error_msg)
                await ws.send_json({"type": "error", "content": error_msg})
                continue

            complete_text = "".join(full_response)
            log.info("Response complete, length=%d chars", len(complete_text))
            history.add("assistant", complete_text)
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
