const { contextBridge, ipcRenderer } = require("electron");

function apiBaseUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("api") || "http://127.0.0.1:0";
}

async function requestJson(path, payload) {
  const options = payload === undefined
    ? { method: "GET" }
    : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      };
  const response = await fetch(`${apiBaseUrl()}${path}`, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

contextBridge.exposeInMainWorld("desktopPetApi", {
  ready: () => requestJson("/api/state"),
  requestState: (state) => requestJson("/api/request-state", { state }),
  chooseStateVideo: async (state) => {
    const path = await ipcRenderer.invoke("desktop-pet:choose-video");
    if (!path) {
      return requestJson("/api/state");
    }
    return requestJson("/api/state-video", { state, path });
  },
  resetStateVideo: (state) => requestJson("/api/reset-state-video", { state }),
  setStateScale: async (state, percent) => {
    await requestJson("/api/state-scale", { state, percent });
    return null;
  },
  setStateSpeed: async (state, percent) => {
    await requestJson("/api/state-speed", { state, percent });
    return null;
  },
  setStateLoopMode: (state, loopMode) => requestJson("/api/state-loop", { state, loopMode }),
  setBlackBackground: (enabled) => requestJson("/api/black-background", { enabled }),
  say: (text) => requestJson("/api/say", { text }),
  chat: (text) => requestJson("/api/chat", { text }),
  playPreview: () => requestJson("/api/play-preview"),
  pausePreview: () => requestJson("/api/pause-preview"),
  syncPreview: () => requestJson("/api/sync-preview"),
  quitApp: async () => {
    try {
      return await requestJson("/api/quit");
    } finally {
      ipcRenderer.send("desktop-pet:quit-shell");
    }
  },
});
