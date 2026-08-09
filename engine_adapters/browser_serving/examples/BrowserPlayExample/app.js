const STORAGE_KEY = "a3game.browser_play.session.v1";

const elements = {
  frame: document.getElementById("streamFrame"),
  surface: document.getElementById("streamSurface"),
  empty: document.getElementById("emptyState"),
  emptyTitle: document.getElementById("emptyTitle"),
  emptyMessage: document.getElementById("emptyMessage"),
  sessionLabel: document.getElementById("sessionLabel"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  focusButton: document.getElementById("focusButton"),
  retryButton: document.getElementById("retryButton"),
  fullscreenButton: document.getElementById("fullscreenButton"),
};

const query = new URLSearchParams(window.location.search);
const state = {
  engine: query.get("engine") || "ue5",
  session: null,
  busy: false,
};

function setStatus(kind, message) {
  elements.statusDot.className = `status-dot ${kind || ""}`.trim();
  elements.statusText.textContent = message;
}

function setBusy(busy) {
  state.busy = busy;
  elements.retryButton.disabled = busy;
}

function showEmpty(title, message, error = false) {
  elements.frame.hidden = true;
  elements.empty.hidden = false;
  elements.emptyTitle.textContent = title;
  elements.emptyMessage.textContent = message;
  setStatus(error ? "error" : "", error ? "Unavailable" : "Starting");
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.ok === false) {
    const errors = Array.isArray(body.errors)
      ? body.errors.join(", ")
      : "";
    throw new Error(errors || body.detail || response.statusText);
  }
  return body.payload && typeof body.payload === "object"
    ? body.payload
    : body;
}

function sessionId(session) {
  return String(
    session?.session_id
      || session?.sessionId
      || session?.id
      || "",
  );
}

function streamUrl(session) {
  return String(
    session?.stream_url
      || session?.pixel_streaming_url
      || session?.pixelStreamingUrl
      || "",
  );
}

function loadStoredSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

function querySession() {
  const value = String(query.get("session") || "").trim();
  if (!value) {
    return null;
  }
  if (value.startsWith("{")) {
    try {
      const parsed = JSON.parse(value);
      if (parsed && typeof parsed === "object") {
        return parsed;
      }
    } catch {
      return { session_id: value };
    }
  }
  return { session_id: value };
}

function recoverySnapshot() {
  const fromQuery = querySession();
  const stored = loadStoredSession();
  if (!fromQuery) {
    return stored;
  }
  if (
    stored
    && sessionId(stored)
    && sessionId(stored) === sessionId(fromQuery)
  ) {
    return { ...stored, ...fromQuery };
  }
  return fromQuery;
}

function storeSession(session) {
  state.session = session;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  const id = sessionId(session);
  elements.sessionLabel.textContent = id || "Active session";
  if (id) {
    const next = new URL(window.location.href);
    next.searchParams.set("session", id);
    next.searchParams.set("engine", state.engine);
    window.history.replaceState({}, "", next);
  }
}

function playbackUrl(url) {
  return new URL(url, window.location.href).toString();
}

function showStream(session) {
  const url = streamUrl(session);
  if (!url) {
    throw new Error(
      "Browser Serving returned a session without stream_url.",
    );
  }
  storeSession(session);
  elements.frame.src = playbackUrl(url);
  elements.frame.hidden = false;
  elements.empty.hidden = true;
  setStatus("", "Waiting for Engine stream");
}

async function createSession() {
  showEmpty(
    "Starting game",
    "Launching the selected Engine runtime and stream session.",
  );
  return request("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      engine: state.engine,
      user_id: `browser_${Date.now().toString(36)}`,
      participant_id: "",
      character: {},
      options: {},
    }),
  });
}

async function recoverSession(snapshot) {
  showEmpty(
    "Recovering game",
    "Reconnecting to the existing Engine stream session.",
  );
  return request("/api/sessions/recover", {
    method: "POST",
    body: JSON.stringify({
      engine: state.engine,
      session: snapshot,
    }),
  });
}

async function bootstrap() {
  if (state.busy) {
    return;
  }
  setBusy(true);
  try {
    setStatus("", "Checking Browser Serving");
    await request("/api/health");

    const snapshot = recoverySnapshot();
    let session;
    if (snapshot && sessionId(snapshot)) {
      try {
        session = await recoverSession(snapshot);
      } catch {
        sessionStorage.removeItem(STORAGE_KEY);
        session = await createSession();
      }
    } else {
      session = await createSession();
    }
    showStream(session);
  } catch (error) {
    showEmpty(
      "Game unavailable",
      error.message || "Browser Serving could not start the game session.",
      true,
    );
  } finally {
    setBusy(false);
  }
}

function focusInput() {
  elements.surface.focus();
  elements.frame.focus();
  elements.frame.contentWindow?.focus();
}

async function toggleFullscreen() {
  if (document.fullscreenElement) {
    await document.exitFullscreen();
  } else {
    await elements.surface.requestFullscreen();
  }
}

elements.focusButton.addEventListener("click", focusInput);
elements.retryButton.addEventListener("click", bootstrap);
elements.fullscreenButton.addEventListener("click", () => {
  toggleFullscreen().catch((error) => {
    setStatus("error", error.message || "Fullscreen failed");
  });
});
elements.frame.addEventListener("load", () => {
  setStatus("ready", "Stream page connected");
  focusInput();
});
elements.surface.addEventListener("pointerdown", focusInput);
window.addEventListener("online", bootstrap);
window.addEventListener("offline", () => {
  setStatus("error", "Network offline");
});

bootstrap();
