let sessionId = null;
let ws = null;
let currentModel = null;
let currentAssistantId = null;
let currentAssistantName = null;
let currentAssistantColor = null;
let isStreaming = false;
let streamBuffer = "";
let activeAssistantEl = null;
let commandHighlightIndex = 0;
let maxInputChars = 32000;
let currentArchiveFilename = null;

const messagesEl = document.getElementById("messages");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const assistantOverlay = document.getElementById("assistant-overlay");
const assistantList = document.getElementById("assistant-list");
const chatContainer = document.getElementById("chat-container");
const headerModel = document.getElementById("header-model");
const commandPopup = document.getElementById("command-popup");
const stopBtn = document.getElementById("stop-btn");
const contextBar = document.getElementById("context-bar");
const headerTitle = document.getElementById("header-title");
const headerAssistantDot = document.getElementById("header-assistant-dot");

const sidebar = document.getElementById("sidebar");
const sidebarRecentsList = document.getElementById("sidebar-recents-list");
const sidebarAssistantInfo = document.getElementById("sidebar-assistant-info");

// --- Constants ---

const ASSISTANT_COLORS = [
  "#6b9fdb", "#4a9f4a", "#e0943a", "#c94040",
  "#9b59b6", "#e67e73", "#45b7aa", "#d4a843",
  "#7e8cc9", "#c0c0c0",
];

const PROMPT_TEMPLATES = {
  general: "You are a helpful assistant. Answer questions clearly and concisely.",
  code: "You are an expert programmer. Help with coding questions, debug issues, and suggest best practices. Always include code examples when relevant.",
  writing: "You are a creative writing assistant. Help with storytelling, editing, and brainstorming ideas. Be encouraging and constructive.",
  blank: "",
};

// --- Command registry ---

const COMMANDS = [
  { name: "/clear", description: "Clear conversation", handler: () => handleClear() },
  { name: "/assistant", description: "Switch assistant", handler: () => handleAssistantSwitch() },
  { name: "/status", description: "Show context usage", handler: () => handleStatus() },
];

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
  console.log("[init] DOMContentLoaded fired, starting init");
  initContextBarSegments();
  initSidebar();
  init();
  loadArchives();
});

async function init() {
  console.log("[init] Fetching assistants");
  try {
    const res = await fetch("/api/assistants");
    const data = await res.json();
    const assistants = data.assistants || [];
    console.log("[init] Assistants received:", assistants.length);

    if (assistants.length === 0) {
      assistantList.innerHTML =
        '<p style="color: var(--error)">No assistants found. Is Ollama running?</p>';
      return;
    }

    renderAssistantPicker(assistants);
  } catch (err) {
    console.error("[init] Failed to fetch assistants:", err);
    assistantList.innerHTML =
      '<p style="color: var(--error)">Cannot connect to server.</p>';
  }
}

// --- Assistant picker ---

function renderAssistantPicker(assistants) {
  assistantList.innerHTML = "";
  assistants.forEach((ast) => {
    const card = document.createElement("div");
    card.className = "assistant-card";
    card.addEventListener("click", () => {
      if (ast.model) {
        selectAssistant(ast.id, ast.model);
      } else {
        toggleModelSubpicker(card, ast);
      }
    });

    const dot = document.createElement("div");
    dot.className = "assistant-card-dot";
    dot.style.backgroundColor = ast.avatar_color || ASSISTANT_COLORS[0];
    card.appendChild(dot);

    const info = document.createElement("div");
    info.className = "assistant-card-info";

    const name = document.createElement("div");
    name.className = "assistant-card-name";
    name.textContent = ast.name;
    info.appendChild(name);

    if (ast.description) {
      const desc = document.createElement("div");
      desc.className = "assistant-card-desc";
      desc.textContent = ast.description;
      info.appendChild(desc);
    }

    if (ast.model) {
      const model = document.createElement("div");
      model.className = "assistant-card-model";
      model.textContent = ast.model;
      info.appendChild(model);
    } else {
      const model = document.createElement("div");
      model.className = "assistant-card-model";
      model.textContent = "select a model";
      model.style.fontStyle = "italic";
      info.appendChild(model);
    }

    card.appendChild(info);

    // Action buttons
    const actions = document.createElement("div");
    actions.className = "assistant-card-actions";

    // Edit button
    const editBtn = document.createElement("button");
    editBtn.className = "assistant-card-edit";
    editBtn.title = "Edit assistant";
    editBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openWizard(ast);
    });
    actions.appendChild(editBtn);

    // Delete button (not for default)
    if (ast.id !== "default") {
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "assistant-card-delete";
      deleteBtn.title = "Delete assistant";
      deleteBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';
      deleteBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
          const res = await fetch(`/api/assistants/${ast.id}`, { method: "DELETE" });
          if (res.ok) {
            card.remove();
          }
        } catch (err) {
          console.error("[assistant] Failed to delete:", err);
        }
      });
      actions.appendChild(deleteBtn);
    }

    card.appendChild(actions);
    assistantList.appendChild(card);
  });
}

function closeAllSubpickers() {
  document.querySelectorAll(".assistant-model-subpicker").forEach((el) => el.remove());
}

async function toggleModelSubpicker(card, ast) {
  // If already showing subpicker on this card, close it
  const existing = card.querySelector(".assistant-model-subpicker");
  if (existing) {
    existing.remove();
    return;
  }

  // Close any other open subpicker first
  closeAllSubpickers();

  const subpicker = document.createElement("div");
  subpicker.className = "assistant-model-subpicker";
  subpicker.innerHTML = '<p style="color: var(--text-dim); font-size: 12px;">Loading models...</p>';
  card.appendChild(subpicker);

  // Close on click outside
  function onClickOutside(e) {
    if (!card.contains(e.target)) {
      subpicker.remove();
      document.removeEventListener("mousedown", onClickOutside);
    }
  }
  setTimeout(() => document.addEventListener("mousedown", onClickOutside), 0);

  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    subpicker.innerHTML = "";
    if (data.models.length === 0) {
      subpicker.innerHTML = '<p style="color: var(--error); font-size: 12px;">No models found</p>';
      return;
    }
    data.models.forEach((model) => {
      const btn = document.createElement("button");
      btn.className = "model-option";
      btn.textContent = model;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        selectAssistant(ast.id, model);
      });
      subpicker.appendChild(btn);
    });
  } catch (err) {
    subpicker.innerHTML = '<p style="color: var(--error); font-size: 12px;">Failed to load models</p>';
  }
}

// --- Assistant selection ---

async function selectAssistant(assistantId, model) {
  console.log("[selectAssistant] id:", assistantId, "model:", model);
  try {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assistant_id: assistantId, model: model }),
    });
    const data = await res.json();
    console.log("[selectAssistant] Session created:", data);
    sessionId = data.session_id;
    currentModel = data.model;
    currentAssistantId = data.assistant_id;
    currentAssistantName = data.assistant_name;
    currentAssistantColor = data.assistant_color;
    currentArchiveFilename = null;

    headerModel.textContent = data.model;
    updateAssistantUI();

    assistantOverlay.style.display = "none";
    chatContainer.style.display = "flex";
    messagesEl.innerHTML = "";
    connectWebSocket();
    updateContextBar();
    loadArchives();
    userInput.focus();
  } catch (err) {
    console.error("[selectAssistant] Failed:", err);
    appendSystemMessage("Failed to create session.");
  }
}

function updateAssistantUI() {
  const banner = document.getElementById("assistant-banner");
  const bannerName = document.getElementById("assistant-banner-name");
  const headerName = document.getElementById("header-assistant-name");

  if (currentAssistantName) {
    // Colored banner strip
    banner.style.display = "flex";
    banner.style.backgroundColor = currentAssistantColor || "var(--accent)";
    bannerName.textContent = currentAssistantName;
    bannerName.style.color = "#fff";

    // Header dot
    headerAssistantDot.style.backgroundColor = currentAssistantColor || "var(--accent)";
    headerAssistantDot.style.display = "inline-block";

    // Header name label
    headerName.textContent = currentAssistantName;
    headerName.style.display = "inline";

    // Input placeholder
    userInput.placeholder = `Message ${currentAssistantName}...`;
  } else {
    banner.style.display = "none";
    headerAssistantDot.style.display = "none";
    headerName.style.display = "none";
    userInput.placeholder = "Message local-llm...";
  }

  // Sidebar footer
  const label = currentAssistantName || "Default";
  const modelLabel = currentModel || "";
  sidebarAssistantInfo.textContent = label + (modelLabel ? " \u00B7 " + modelLabel : "");
}

// --- Streaming UI toggle ---

function setStreamingUI(streaming) {
  sendBtn.style.display = streaming ? "none" : "flex";
  stopBtn.style.display = streaming ? "flex" : "none";
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
    } else if (msg.type === "stopped") {
      console.log("[ws] Stream stopped by user, partial length:", msg.content.length);
      finishStreaming(msg.content || null);
    } else if (msg.type === "title") {
      console.log("[ws] Title received:", msg.content);
      headerTitle.textContent = msg.content;
      document.title = msg.content + " \u2014 local-llm";
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
  setStreamingUI(true);
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
    if (finalContent) {
      contentEl.innerHTML = renderMarkdown(finalContent);
      contentEl.querySelectorAll("pre code").forEach((el) => {
        hljs.highlightElement(el);
      });
    } else if (finalContent === null || finalContent === "") {
      // Remove empty assistant bubble (e.g. stopped before any tokens)
      activeAssistantEl.remove();
    }
  }
  isStreaming = false;
  setStreamingUI(false);
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
    currentArchiveFilename = null;
    messagesEl.innerHTML = "";
    headerTitle.textContent = "local-llm";
    document.title = "local-llm";
    connectWebSocket();
    updateContextBar();
    loadArchives();
    appendSystemMessage("Conversation cleared.");
  } catch (err) {
    console.error("[clear] Failed:", err);
    appendSystemMessage("Failed to clear session.");
  }
}

async function handleAssistantSwitch() {
  console.log("[assistant] Switching assistant, closing WebSocket");
  currentArchiveFilename = null;
  assistantOverlay.style.display = "flex";
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

    const assistantLine = data.assistant_name
      ? `<span class="status-label">Assistant:</span>
         <span class="status-value">${data.assistant_name}</span>`
      : "";

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
        ${assistantLine}
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
  if (role === "user") {
    roleLabel.textContent = "You";
  } else if (role === "assistant") {
    roleLabel.textContent = currentAssistantName || "Assistant";
  } else {
    roleLabel.textContent = "System";
  }
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
    if (e.key === "Escape" && isStreaming) {
      e.preventDefault();
      stopBtn.click();
      return;
    }
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

stopBtn.addEventListener("click", () => {
  if (!isStreaming || !ws) return;
  console.log("[stop] Sending stop signal");
  ws.send("__STOP__");
});

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
document.getElementById("assistant-btn").addEventListener("click", handleAssistantSwitch);

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
      document.title = newTitle + " \u2014 local-llm";
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
    currentArchiveFilename = null;
    messagesEl.innerHTML = "";
    headerTitle.textContent = "local-llm";
    document.title = "local-llm";
    connectWebSocket();
    updateContextBar();
    loadArchives();
  } catch (err) {
    console.error("[context-clear] Failed:", err);
  }

  btn.disabled = false;
  btn.textContent = "Clear Context";
  modal.classList.remove("clearing");
  closeContextModal();
});

// --- Sidebar ---

function initSidebar() {
  const collapsed = localStorage.getItem("sidebar-collapsed") === "true";
  if (collapsed) {
    sidebar.classList.add("collapsed");
  }
}

function toggleSidebar() {
  sidebar.classList.toggle("collapsed");
  localStorage.setItem("sidebar-collapsed", sidebar.classList.contains("collapsed"));
}

async function loadArchives() {
  console.log("[sidebar] Loading archives");
  try {
    const res = await fetch("/api/archives");
    const data = await res.json();
    const archives = data.archives || [];
    console.log("[sidebar] Archives loaded:", archives.length);

    if (archives.length === 0) {
      sidebarRecentsList.innerHTML = '<div class="sidebar-recents-empty">No conversations yet</div>';
      return;
    }

    sidebarRecentsList.innerHTML = "";
    archives.forEach((arc) => {
      const btn = document.createElement("button");
      btn.className = "sidebar-recent-item";
      btn.title = arc.title;
      btn.addEventListener("click", () => loadConversation(arc.filename, btn, arc.assistant_id));

      // Assistant color dot
      if (arc.assistant_name) {
        const dot = document.createElement("span");
        dot.className = "assistant-dot-sm";
        // Use a consistent color lookup or default
        dot.style.backgroundColor = arc.assistant_color || ASSISTANT_COLORS[0];
        btn.appendChild(dot);
      }

      const titleSpan = document.createElement("span");
      titleSpan.className = "sidebar-recent-title";
      titleSpan.textContent = arc.title;
      btn.appendChild(titleSpan);

      const deleteSpan = document.createElement("span");
      deleteSpan.className = "sidebar-recent-delete";
      deleteSpan.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>';
      deleteSpan.title = "Delete conversation";
      deleteSpan.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
          const res = await fetch(`/api/archives/${arc.filename}`, { method: "DELETE" });
          if (res.ok) {
            btn.remove();
            if (btn.classList.contains("active")) {
              messagesEl.innerHTML = "";
            }
            if (sidebarRecentsList.children.length === 0) {
              sidebarRecentsList.innerHTML = '<div class="sidebar-recents-empty">No conversations yet</div>';
            }
          }
        } catch (err) {
          console.error("[sidebar] Failed to delete archive:", err);
        }
      });
      btn.appendChild(deleteSpan);

      sidebarRecentsList.appendChild(btn);
    });
  } catch (err) {
    console.error("[sidebar] Failed to load archives:", err);
    sidebarRecentsList.innerHTML = '<div class="sidebar-recents-empty">Failed to load</div>';
  }
}

async function loadConversation(filename, btnEl, archiveAssistantId) {
  console.log("[sidebar] Loading conversation:", filename);

  if (filename === currentArchiveFilename) {
    console.log("[sidebar] Already viewing this archive, skipping");
    return;
  }

  if (!currentModel && !archiveAssistantId) {
    console.log("[sidebar] No model/assistant selected, showing overlay");
    assistantOverlay.style.display = "flex";
    return;
  }

  try {
    // Archive current session before switching
    if (sessionId) {
      console.log("[sidebar] Archiving current session before switch:", sessionId);
      await fetch(`/api/sessions/${sessionId}/clear`, { method: "POST" });
    }

    // Resume: create a new session seeded with archived messages
    const resumeBody = { filename };
    if (archiveAssistantId) {
      resumeBody.assistant_id = archiveAssistantId;
    }
    if (currentModel) {
      resumeBody.model = currentModel;
    }

    const resumeRes = await fetch("/api/sessions/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(resumeBody),
    });
    if (!resumeRes.ok) {
      appendSystemMessage("Failed to resume conversation.");
      return;
    }
    const resumeData = await resumeRes.json();
    console.log("[sidebar] Session resumed:", resumeData);

    sessionId = resumeData.session_id;
    currentModel = resumeData.model;
    currentAssistantId = resumeData.assistant_id;
    currentAssistantName = resumeData.assistant_name;
    currentAssistantColor = resumeData.assistant_color;

    headerModel.textContent = resumeData.model;
    updateAssistantUI();
    connectWebSocket();

    // Update header title if archive had one
    if (resumeData.title) {
      headerTitle.textContent = resumeData.title;
      document.title = resumeData.title + " \u2014 local-llm";
    }

    // Fetch archived messages for display
    const archiveRes = await fetch(`/api/archives/${filename}`);
    if (!archiveRes.ok) {
      appendSystemMessage("Failed to load conversation messages.");
      return;
    }
    const archiveData = await archiveRes.json();
    const messages = archiveData.messages || [];

    // Highlight active item
    sidebarRecentsList.querySelectorAll(".sidebar-recent-item").forEach((el) => {
      el.classList.remove("active");
    });
    if (btnEl) btnEl.classList.add("active");

    // Display archived messages
    messagesEl.innerHTML = "";
    messages.forEach((msg) => {
      if (msg.role === "system") return;
      appendMessage(msg.role, msg.content);
    });

    // Show the chat container if not visible
    if (chatContainer.style.display === "none") {
      assistantOverlay.style.display = "none";
      chatContainer.style.display = "flex";
    }

    currentArchiveFilename = filename;
    updateContextBar();
    loadArchives();
    scrollToBottom();
    userInput.focus();
  } catch (err) {
    console.error("[sidebar] Failed to load conversation:", err);
    appendSystemMessage("Failed to load conversation.");
  }
}

// Sidebar event listeners
document.getElementById("sidebar-toggle").addEventListener("click", toggleSidebar);
document.getElementById("sidebar-new-chat").addEventListener("click", handleClear);
document.getElementById("sidebar-switch-assistant").addEventListener("click", handleAssistantSwitch);

// --- Assistant Wizard ---

let wizardStep = 1;
let wizardEditId = null;
let wizardSelectedColor = ASSISTANT_COLORS[0];
let wizardSelectedModel = null;

function openWizard(existingAssistant = null) {
  const overlay = document.getElementById("assistant-wizard-overlay");
  wizardStep = 1;
  wizardEditId = existingAssistant ? existingAssistant.id : null;

  // Set title
  document.getElementById("wizard-title").textContent =
    existingAssistant ? "Edit Assistant" : "Create Assistant";

  // Pre-fill if editing
  document.getElementById("wizard-name").value = existingAssistant ? existingAssistant.name : "";
  document.getElementById("wizard-description").value = existingAssistant ? (existingAssistant.description || "") : "";
  document.getElementById("wizard-system-prompt").value = existingAssistant ? existingAssistant.system_prompt : "";

  // Context overrides
  document.getElementById("wizard-context-tokens").value = existingAssistant?.context_tokens || "";
  document.getElementById("wizard-token-ratio").value = existingAssistant?.token_estimate_ratio || "";
  document.getElementById("wizard-context-reserve").value = existingAssistant?.context_reserve || "";

  // Color
  wizardSelectedColor = existingAssistant?.avatar_color || ASSISTANT_COLORS[0];
  renderColorSwatches();

  // Model
  wizardSelectedModel = existingAssistant?.model || null;
  loadModelsForWizard();

  // Reset errors
  document.querySelectorAll(".wizard-error").forEach((el) => el.textContent = "");

  // Show step 1
  showWizardStep(1);

  // Save button text
  document.getElementById("wizard-save").textContent =
    existingAssistant ? "Save Changes" : "Create Assistant";

  overlay.style.display = "flex";
}

function closeWizard() {
  document.getElementById("assistant-wizard-overlay").style.display = "none";
  wizardEditId = null;
}

function showWizardStep(step) {
  wizardStep = step;
  for (let i = 1; i <= 4; i++) {
    document.getElementById(`wizard-step-${i}`).style.display = i === step ? "" : "none";
  }

  // Update step indicator
  document.querySelectorAll(".wizard-step-dot").forEach((dot) => {
    const s = parseInt(dot.dataset.step);
    dot.classList.toggle("active", s === step);
    dot.classList.toggle("completed", s < step);
  });
  document.querySelectorAll(".wizard-step-line").forEach((line, i) => {
    line.classList.toggle("completed", i + 1 < step);
  });

  // Show/hide back/next/save
  document.getElementById("wizard-back").style.display = step > 1 ? "" : "none";
  document.getElementById("wizard-next").style.display = step < 4 ? "" : "none";
  document.getElementById("wizard-save").style.display = step === 4 ? "" : "none";
}

function renderColorSwatches() {
  const container = document.getElementById("wizard-color-swatches");
  container.innerHTML = "";
  ASSISTANT_COLORS.forEach((color) => {
    const swatch = document.createElement("div");
    swatch.className = "color-swatch" + (color === wizardSelectedColor ? " selected" : "");
    swatch.style.backgroundColor = color;
    swatch.addEventListener("click", () => {
      wizardSelectedColor = color;
      container.querySelectorAll(".color-swatch").forEach((s) => s.classList.remove("selected"));
      swatch.classList.add("selected");
    });
    container.appendChild(swatch);
  });
}

async function loadModelsForWizard() {
  const grid = document.getElementById("wizard-model-list");
  grid.innerHTML = '<p style="color: var(--text-dim); font-size: 12px;">Loading models...</p>';
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    grid.innerHTML = "";
    data.models.forEach((model) => {
      const btn = document.createElement("button");
      btn.className = "model-option" + (model === wizardSelectedModel ? " selected" : "");
      btn.textContent = model;
      btn.addEventListener("click", () => {
        wizardSelectedModel = model;
        grid.querySelectorAll(".model-option").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        document.getElementById("wizard-model-error").textContent = "";
      });
      grid.appendChild(btn);
    });
  } catch (err) {
    grid.innerHTML = '<p style="color: var(--error); font-size: 12px;">Failed to load models</p>';
  }
}

function validateWizardStep(step) {
  if (step === 1) {
    const name = document.getElementById("wizard-name").value.trim();
    if (!name) {
      document.getElementById("wizard-name-error").textContent = "Name is required";
      return false;
    }
    document.getElementById("wizard-name-error").textContent = "";
    return true;
  }
  if (step === 2) {
    // Model is optional for default assistant, required for custom
    if (wizardEditId !== "default" && !wizardSelectedModel) {
      document.getElementById("wizard-model-error").textContent = "Please select a model";
      return false;
    }
    document.getElementById("wizard-model-error").textContent = "";
    return true;
  }
  if (step === 3) {
    const prompt = document.getElementById("wizard-system-prompt").value.trim();
    if (!prompt) {
      document.getElementById("wizard-prompt-error").textContent = "System prompt is required";
      return false;
    }
    document.getElementById("wizard-prompt-error").textContent = "";
    return true;
  }
  return true;
}

async function saveWizard() {
  // Validate step 3 even if on step 4
  if (!validateWizardStep(3)) {
    showWizardStep(3);
    return;
  }

  const config = {
    name: document.getElementById("wizard-name").value.trim(),
    description: document.getElementById("wizard-description").value.trim() || null,
    avatar_color: wizardSelectedColor,
    model: wizardSelectedModel,
    system_prompt: document.getElementById("wizard-system-prompt").value.trim(),
  };

  // Optional advanced fields
  const contextTokens = document.getElementById("wizard-context-tokens").value;
  if (contextTokens) config.context_tokens = parseInt(contextTokens);

  const tokenRatio = document.getElementById("wizard-token-ratio").value;
  if (tokenRatio) config.token_estimate_ratio = parseFloat(tokenRatio);

  const contextReserve = document.getElementById("wizard-context-reserve").value;
  if (contextReserve) config.context_reserve = parseInt(contextReserve);

  try {
    let res;
    if (wizardEditId) {
      res = await fetch(`/api/assistants/${wizardEditId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
    } else {
      res = await fetch("/api/assistants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
    }

    if (!res.ok) {
      const err = await res.json();
      document.getElementById("wizard-prompt-error").textContent = err.detail || "Save failed";
      return;
    }

    closeWizard();
    // Refresh the assistant picker
    await init();
  } catch (err) {
    console.error("[wizard] Save failed:", err);
  }
}

// Wizard event listeners
document.getElementById("create-assistant-btn").addEventListener("click", () => openWizard());
document.getElementById("wizard-close-btn").addEventListener("click", closeWizard);
document.getElementById("wizard-cancel").addEventListener("click", closeWizard);

document.getElementById("wizard-next").addEventListener("click", () => {
  if (validateWizardStep(wizardStep)) {
    showWizardStep(wizardStep + 1);
  }
});

document.getElementById("wizard-back").addEventListener("click", () => {
  showWizardStep(wizardStep - 1);
});

document.getElementById("wizard-save").addEventListener("click", saveWizard);

// Template buttons
document.querySelectorAll(".template-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const template = btn.dataset.template;
    document.getElementById("wizard-system-prompt").value = PROMPT_TEMPLATES[template] || "";
    document.querySelectorAll(".template-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("wizard-prompt-error").textContent = "";
  });
});

// Advanced toggle
document.getElementById("wizard-advanced-toggle").addEventListener("click", () => {
  const toggle = document.getElementById("wizard-advanced-toggle");
  const content = document.getElementById("wizard-advanced-content");
  const isOpen = content.style.display !== "none";
  content.style.display = isOpen ? "none" : "";
  toggle.classList.toggle("open", !isOpen);
});

// Close wizard on overlay click (outside modal)
document.getElementById("assistant-wizard-overlay").addEventListener("click", (e) => {
  if (e.target === document.getElementById("assistant-wizard-overlay")) {
    closeWizard();
  }
});
