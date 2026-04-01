let sessionId = null;
let ws = null;
let currentModel = null;
let isStreaming = false;
let streamBuffer = "";
let activeAssistantEl = null;
let commandHighlightIndex = 0;
let maxInputChars = 32000;

const messagesEl = document.getElementById("messages");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const modelOverlay = document.getElementById("model-overlay");
const modelList = document.getElementById("model-list");
const chatContainer = document.getElementById("chat-container");
const headerModel = document.getElementById("header-model");
const commandPopup = document.getElementById("command-popup");
const contextBar = document.getElementById("context-bar");
const headerTitle = document.getElementById("header-title");

// --- Command registry ---

const COMMANDS = [
  { name: "/clear", description: "Clear conversation", handler: () => handleClear() },
  { name: "/model", description: "Switch model", handler: () => handleModelSwitch() },
  { name: "/status", description: "Show context usage", handler: () => handleStatus() },
];

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
  console.log("[init] DOMContentLoaded fired, starting init");
  initContextBarSegments();
  init();
});

async function init() {
  console.log("[init] Fetching models from /api/models");
  try {
    const res = await fetch("/api/models");
    console.log("[init] /api/models response status:", res.status);
    const data = await res.json();
    console.log("[init] Models received:", data.models);
    if (data.models.length === 0) {
      console.warn("[init] No models found");
      modelList.innerHTML =
        '<p style="color: var(--error)">No models found. Is Ollama running?</p>';
      return;
    }
    modelList.innerHTML = "";
    data.models.forEach((model) => {
      const btn = document.createElement("button");
      btn.className = "model-option";
      btn.textContent = model;
      btn.addEventListener("click", () => selectModel(model));
      modelList.appendChild(btn);
    });
    console.log("[init] Model buttons rendered:", data.models.length);
  } catch (err) {
    console.error("[init] Failed to fetch models:", err);
    modelList.innerHTML =
      '<p style="color: var(--error)">Cannot connect to server.</p>';
  }
}

// --- Model selection ---

async function selectModel(model) {
  console.log("[selectModel] Selected model:", model);
  try {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    console.log("[selectModel] /api/sessions response status:", res.status);
    const data = await res.json();
    console.log("[selectModel] Session created:", data);
    sessionId = data.session_id;
    currentModel = model;
    headerModel.textContent = model;
    modelOverlay.style.display = "none";
    chatContainer.style.display = "flex";
    messagesEl.innerHTML = "";
    connectWebSocket();
    updateContextBar();
    userInput.focus();
  } catch (err) {
    console.error("[selectModel] Failed to create session:", err);
    appendSystemMessage("Failed to create session.");
  }
}

// --- WebSocket ---

function connectWebSocket() {
  if (ws) {
    console.log("[ws] Closing previous WebSocket");
    ws.close();
  }
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${location.host}/ws/chat/${sessionId}`;
  console.log("[ws] Connecting to:", url);
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log("[ws] Connection opened");
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log("[ws] Message received:", msg.type, msg.type === "token" ? JSON.stringify(msg.content).slice(0, 50) : msg.content);

    if (msg.type === "token") {
      streamBuffer += msg.content;
      renderStreamingContent();
    } else if (msg.type === "done") {
      console.log("[ws] Stream complete, total length:", msg.content.length);
      finishStreaming(msg.content);
    } else if (msg.type === "title") {
      console.log("[ws] Title received:", msg.content);
      headerTitle.textContent = msg.content;
      document.title = msg.content + " — local-llm";
    } else if (msg.type === "error") {
      console.error("[ws] Error from server:", msg.content);
      finishStreaming(null);
      appendSystemMessage(`Error: ${msg.content}`);
    }
  };

  ws.onclose = (event) => {
    console.log("[ws] Connection closed, code:", event.code, "reason:", event.reason, "wasClean:", event.wasClean);
    if (isStreaming) {
      console.warn("[ws] Connection lost while streaming");
      finishStreaming(null);
      appendSystemMessage("Connection lost.");
    }
  };

  ws.onerror = (event) => {
    console.error("[ws] WebSocket error:", event);
  };
}

// --- Sending messages ---

function sendMessage() {
  const text = userInput.value.trim();
  if (!text || isStreaming) {
    console.log("[send] Blocked: empty=", !text, "streaming=", isStreaming);
    return;
  }
  if (text.length > maxInputChars) {
    console.log("[send] Blocked: message too long", text.length, ">", maxInputChars);
    return;
  }

  console.log("[send] Sending user message:", text);
  console.log("[send] WebSocket readyState:", ws ? ws.readyState : "null", "(0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)");

  appendMessage("user", text);
  userInput.value = "";
  resetTextarea();

  isStreaming = true;
  streamBuffer = "";
  activeAssistantEl = appendMessage("assistant", "");
  activeAssistantEl
    .querySelector(".message-content")
    .classList.add("streaming-cursor");

  ws.send(text);
  console.log("[send] Message sent via WebSocket");
}

// --- Streaming render ---

function renderStreamingContent() {
  if (!activeAssistantEl) return;
  const contentEl = activeAssistantEl.querySelector(".message-content");
  contentEl.innerHTML = renderMarkdown(streamBuffer);
  scrollToBottom();
}

function finishStreaming(finalContent) {
  console.log("[stream] Finishing stream, finalContent:", finalContent !== null ? "present" : "null");
  if (activeAssistantEl) {
    const contentEl = activeAssistantEl.querySelector(".message-content");
    contentEl.classList.remove("streaming-cursor");
    if (finalContent !== null) {
      contentEl.innerHTML = renderMarkdown(finalContent);
      contentEl.querySelectorAll("pre code").forEach((el) => {
        hljs.highlightElement(el);
      });
    }
  }
  isStreaming = false;
  streamBuffer = "";
  activeAssistantEl = null;
  scrollToBottom();
  updateContextBar();
}

// --- Command popup ---

function showCommandPopup(filter) {
  const matching = COMMANDS.filter((cmd) =>
    cmd.name.startsWith(filter.toLowerCase())
  );
  console.log("[popup] Showing commands, filter:", filter, "matches:", matching.length);

  if (matching.length === 0) {
    hideCommandPopup();
    return;
  }

  commandHighlightIndex = Math.min(commandHighlightIndex, matching.length - 1);

  commandPopup.innerHTML = matching
    .map(
      (cmd, i) =>
        `<div class="command-item${i === commandHighlightIndex ? " highlighted" : ""}" data-index="${i}">
          <span class="command-name">${cmd.name}</span>
          <span class="command-desc">${cmd.description}</span>
        </div>`
    )
    .join("");

  commandPopup.classList.add("visible");

  commandPopup.querySelectorAll(".command-item").forEach((el) => {
    el.addEventListener("click", () => {
      const idx = parseInt(el.dataset.index);
      selectCommand(matching[idx]);
    });
    el.addEventListener("mouseenter", () => {
      commandHighlightIndex = parseInt(el.dataset.index);
      updatePopupHighlight();
    });
  });
}

function hideCommandPopup() {
  commandPopup.classList.remove("visible");
  commandPopup.innerHTML = "";
  commandHighlightIndex = 0;
}

function isPopupVisible() {
  return commandPopup.classList.contains("visible");
}

function selectCommand(cmd) {
  console.log("[popup] Selected command:", cmd.name);
  userInput.value = "";
  resetTextarea();
  hideCommandPopup();
  cmd.handler();
}

function updatePopupHighlight() {
  commandPopup.querySelectorAll(".command-item").forEach((el, i) => {
    el.classList.toggle("highlighted", i === commandHighlightIndex);
  });
}

function getFilteredCommands() {
  const text = userInput.value;
  return COMMANDS.filter((cmd) => cmd.name.startsWith(text.toLowerCase()));
}

// --- Commands ---

async function handleClear() {
  console.log("[clear] Clearing session:", sessionId);
  try {
    const res = await fetch(`/api/sessions/${sessionId}/clear`, {
      method: "POST",
    });
    console.log("[clear] Response status:", res.status);
    const data = await res.json();
    console.log("[clear] New session:", data);
    sessionId = data.session_id;
    messagesEl.innerHTML = "";
    headerTitle.textContent = "local-llm";
    document.title = "local-llm";
    connectWebSocket();
    updateContextBar();
    appendSystemMessage("Conversation cleared.");
  } catch (err) {
    console.error("[clear] Failed:", err);
    appendSystemMessage("Failed to clear session.");
  }
}

async function handleModelSwitch() {
  console.log("[model] Switching model, closing WebSocket");
  modelOverlay.style.display = "flex";
  chatContainer.style.display = "none";
  if (ws) ws.close();
  await init();
}

async function handleStatus() {
  console.log("[status] Fetching status for session:", sessionId);
  try {
    const res = await fetch(`/api/sessions/${sessionId}/status`);
    const data = await res.json();
    const pct = Math.min(100, data.pct_used);
    console.log("[status] Data:", data);

    document.getElementById("context-modal-body").innerHTML = `
      <div class="status-grid">
        <span class="status-label">Context:</span>
        <span class="status-value">${pct}% used (${data.tokens_used.toLocaleString()} / ${data.token_budget.toLocaleString()} tokens)</span>
        <span class="status-label">Q&A:</span>
        <span class="status-value">${data.qa_count} exchanges</span>
        <span class="status-label">Summaries:</span>
        <span class="status-value">${data.summary_count}</span>
        <span class="status-label">Model:</span>
        <span class="status-value">${data.model}</span>
      </div>`;

    const overlay = document.getElementById("context-overlay");
    const modal = overlay.querySelector(".context-modal");
    modal.classList.remove("clearing");
    document.getElementById("context-clear-btn").textContent = "Clear Context";
    document.getElementById("context-close-btn").style.display = "";
    overlay.style.display = "flex";
    updateContextBar();
  } catch (err) {
    console.error("[status] Failed:", err);
    appendSystemMessage("Failed to fetch status.");
  }
}

function closeContextModal() {
  document.getElementById("context-overlay").style.display = "none";
}

// --- Context bar ---

function initContextBarSegments() {
  const container = document.querySelector(".context-segments");
  for (let i = 0; i < 10; i++) {
    const seg = document.createElement("div");
    seg.className = "context-segment";
    container.appendChild(seg);
  }
  console.log("[contextBar] Initialized 10 segments");
}

async function updateContextBar() {
  if (!sessionId) return;
  console.log("[contextBar] Updating context bar");
  try {
    const res = await fetch(`/api/sessions/${sessionId}/status`);
    const data = await res.json();
    const pct = Math.min(100, data.pct_used);
    const filled = Math.min(10, Math.round(pct / 10));
    const color = pct > 80 ? "red" : pct > 50 ? "amber" : "green";

    document.querySelectorAll(".context-segment").forEach((seg, i) => {
      seg.className = "context-segment" + (i < filled ? ` filled ${color}` : "");
    });
    document.querySelector(".context-pct").textContent = `${Math.round(pct)}%`;
    if (data.max_input_chars != null) {
      maxInputChars = data.max_input_chars;
      updateInputLimit();
    }
    const empty = data.qa_count === 0;
    document.getElementById("clear-btn").disabled = empty;
    document.getElementById("context-clear-btn").disabled = empty;
    console.log("[contextBar] Updated: pct=%s filled=%d color=%s maxInput=%d", pct, filled, color, maxInputChars);
  } catch (err) {
    console.error("[contextBar] Failed to update:", err);
  }
}

// --- DOM helpers ---

function appendMessage(role, content) {
  console.log("[dom] Appending message, role:", role, "content length:", content.length);
  const el = document.createElement("div");
  el.className = `message ${role}`;

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "You" : "Assistant";
  el.appendChild(roleLabel);

  const contentEl = document.createElement("div");
  contentEl.className = "message-content";
  if (content) {
    contentEl.innerHTML = renderMarkdown(content);
  }
  el.appendChild(contentEl);

  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
}

function appendSystemMessage(content, isHtml = false) {
  console.log("[dom] Appending system message");
  const el = document.createElement("div");
  el.className = "message system";

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = "System";
  el.appendChild(roleLabel);

  const contentEl = document.createElement("div");
  contentEl.className = "message-content";
  if (isHtml) {
    contentEl.innerHTML = content;
  } else {
    contentEl.textContent = content;
  }
  el.appendChild(contentEl);

  messagesEl.appendChild(el);
  scrollToBottom();
}

function renderMarkdown(text) {
  return marked.parse(text, { breaks: true, gfm: true });
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// --- Input handling ---

userInput.addEventListener("keydown", (e) => {
  if (isPopupVisible()) {
    const matching = getFilteredCommands();

    if (e.key === "ArrowDown") {
      e.preventDefault();
      commandHighlightIndex = Math.min(commandHighlightIndex + 1, matching.length - 1);
      updatePopupHighlight();
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      commandHighlightIndex = Math.max(commandHighlightIndex - 1, 0);
      updatePopupHighlight();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (matching[commandHighlightIndex]) {
        selectCommand(matching[commandHighlightIndex]);
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      hideCommandPopup();
      userInput.value = "";
      resetTextarea();
      return;
    }
    if (e.key === "Tab") {
      e.preventDefault();
      if (matching[commandHighlightIndex]) {
        userInput.value = matching[commandHighlightIndex].name;
      }
      return;
    }
  } else {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
});

userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 200) + "px";

  const text = userInput.value;
  if (text.startsWith("/") && text.indexOf(" ") === -1) {
    commandHighlightIndex = 0;
    showCommandPopup(text);
  } else {
    hideCommandPopup();
  }

  updateInputLimit();
});

sendBtn.addEventListener("click", sendMessage);

function resetTextarea() {
  userInput.style.height = "auto";
  updateInputLimit();
}

// --- Input limit ---

function updateInputLimit() {
  const len = userInput.value.length;
  const hintEl = document.getElementById("input-hint");
  const pct = maxInputChars > 0 ? len / maxInputChars : 0;

  if (pct < 0.5) {
    hintEl.textContent = "Enter to send, Shift+Enter for newline";
    hintEl.style.color = "";
    sendBtn.disabled = false;
    return;
  }

  const display = `${len.toLocaleString()} / ${maxInputChars.toLocaleString()} chars`;

  if (pct >= 1.0) {
    hintEl.textContent = `Message too long (${display})`;
    hintEl.style.color = "var(--error)";
    sendBtn.disabled = true;
  } else if (pct >= 0.9) {
    hintEl.textContent = display;
    hintEl.style.color = "var(--error)";
    sendBtn.disabled = false;
  } else {
    hintEl.textContent = display;
    hintEl.style.color = "var(--text-secondary)";
    sendBtn.disabled = false;
  }
}

// --- Header button handlers ---

contextBar.addEventListener("click", handleStatus);
document.getElementById("clear-btn").addEventListener("click", handleClear);
document.getElementById("model-btn").addEventListener("click", handleModelSwitch);

// --- Editable title ---

headerTitle.addEventListener("click", () => {
  if (!sessionId) return;
  const current = headerTitle.textContent;
  const input = document.createElement("input");
  input.type = "text";
  input.value = current === "local-llm" ? "" : current;
  input.className = "title-edit";
  input.placeholder = "Chat title...";
  headerTitle.replaceWith(input);
  input.focus();
  input.select();

  async function commit() {
    const newTitle = input.value.trim();
    input.replaceWith(headerTitle);
    if (newTitle && newTitle !== current) {
      headerTitle.textContent = newTitle;
      document.title = newTitle + " — local-llm";
      try {
        await fetch(`/api/sessions/${sessionId}/title`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: newTitle }),
        });
        console.log("[title] Renamed to:", newTitle);
      } catch (err) {
        console.error("[title] Rename failed:", err);
      }
    }
  }

  input.addEventListener("blur", commit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); input.blur(); }
    if (e.key === "Escape") { input.value = current; input.blur(); }
  });
});

// --- Context modal ---

document.getElementById("context-close-btn").addEventListener("click", closeContextModal);

document.getElementById("context-overlay").addEventListener("click", (e) => {
  const modal = document.querySelector(".context-modal");
  if (!modal.classList.contains("clearing") && !modal.contains(e.target)) {
    closeContextModal();
  }
});

document.getElementById("context-clear-btn").addEventListener("click", async () => {
  const modal = document.querySelector(".context-modal");
  const btn = document.getElementById("context-clear-btn");
  modal.classList.add("clearing");
  document.getElementById("context-close-btn").style.display = "none";
  btn.textContent = "Clearing...";
  btn.disabled = true;

  try {
    const res = await fetch(`/api/sessions/${sessionId}/clear`, { method: "POST" });
    const data = await res.json();
    sessionId = data.session_id;
    messagesEl.innerHTML = "";
    headerTitle.textContent = "local-llm";
    document.title = "local-llm";
    connectWebSocket();
    updateContextBar();
  } catch (err) {
    console.error("[context-clear] Failed:", err);
  }

  btn.disabled = false;
  btn.textContent = "Clear Context";
  modal.classList.remove("clearing");
  closeContextModal();
});
