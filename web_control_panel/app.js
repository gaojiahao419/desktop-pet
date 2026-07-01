const STATES = [
  { state: "idle", title: "待机动作", subtitle: "平静待机循环" },
  { state: "happy", title: "高兴动作", subtitle: "点击或切换开心时播放" },
  { state: "angry", title: "生气动作", subtitle: "生气状态循环" },
  { state: "sleep", title: "睡觉动作", subtitle: "睡觉状态循环" },
];

const THEME_STORAGE_KEY = "desktop-pet-control-theme";
const THEMES = ["obsidian", "bluegray"];

const appState = {
  bridge: null,
  revision: null,
  theme: localStorage.getItem(THEME_STORAGE_KEY) || "obsidian",
  states: Object.fromEntries(
    STATES.map((item) => [
      item.state,
      {
        ...item,
        materialName: "未绑定，使用内置绘制",
        status: item.subtitle,
        scalePercent: 100,
        speedPercent: 100,
        loopMode: "loop",
      },
    ])
  ),
  actions: [
    { label: "待机", state: "idle", role: "lightButton" },
    { label: "开心", state: "happy", role: "orangeButton" },
    { label: "生气", state: "angry", role: "dangerButton" },
    { label: "睡觉", state: "sleep", role: "lightButton" },
    { label: "隐藏", state: "hide", role: "darkButton" },
    { label: "显示", state: "show", role: "orangeButton" },
  ],
  blackBackground: false,
  status: "状态：使用内置绘制宠物",
  isDraggingRange: false,
  preview: {
    message: "上传素材后显示首帧预览",
    image: "",
    frameLabel: "当前帧：0 / 0",
    state: "",
    playing: false,
  },
};

function byId(id) {
  return document.getElementById(id);
}

function applyTheme(theme, persist = true) {
  const nextTheme = THEMES.includes(theme) ? theme : "obsidian";
  appState.theme = nextTheme;
  document.body.dataset.theme = nextTheme;
  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.themeOption === nextTheme);
  });
  if (persist) {
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  }
}

function callBridge(method, ...args) {
  if (!appState.bridge || typeof appState.bridge[method] !== "function") {
    byId("connectionStatus").textContent = "控制台未连接";
    return;
  }
  try {
    handleBridgeResult(appState.bridge[method](...args));
  } catch (error) {
    byId("connectionStatus").textContent = "连接异常";
    console.error(error);
  }
}

function handleBridgeResult(result) {
  if (!result) {
    return;
  }
  if (typeof result.then === "function") {
    result
      .then((payload) => {
        if (payload) {
          applyPatch(payload);
        }
      })
      .catch((error) => {
        byId("connectionStatus").textContent = "连接异常";
        console.error(error);
      });
    return;
  }
  if (typeof result === "object") {
    applyPatch(result);
  }
}

function refreshFromBridge() {
  if (appState.isDraggingRange || !appState.bridge || typeof appState.bridge.ready !== "function") {
    return;
  }
  handleBridgeResult(appState.bridge.ready());
}

function normalizeRangeValue(rangeInput, rawValue) {
  const min = Number(rangeInput.min || 0);
  const max = Number(rangeInput.max || 100);
  const step = rangeInput.step && rangeInput.step !== "any" ? Number(rangeInput.step) : 1;
  const clamped = Math.max(min, Math.min(max, rawValue));
  return Math.round((clamped - min) / step) * step + min;
}

function rangeValueFromClientX(rangeInput, clientX) {
  const rect = rangeInput.getBoundingClientRect();
  const min = Number(rangeInput.min || 0);
  const max = Number(rangeInput.max || 100);
  const ratio = rect.width <= 0 ? 0 : Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  return normalizeRangeValue(rangeInput, min + ratio * (max - min));
}

function thumbCenterForRange(rangeInput) {
  const rect = rangeInput.getBoundingClientRect();
  const min = Number(rangeInput.min || 0);
  const max = Number(rangeInput.max || 100);
  const value = Number(rangeInput.value || min);
  const ratio = max === min ? 0 : (value - min) / (max - min);
  return rect.left + ratio * rect.width;
}

function createBridgeScheduler(method, state) {
  let pendingValue = null;
  let frameId = 0;

  function flush() {
    frameId = 0;
    if (pendingValue === null) {
      return;
    }
    const value = pendingValue;
    pendingValue = null;
    callBridge(method, state, value);
  }

  function schedule(value) {
    pendingValue = value;
    if (!frameId) {
      frameId = requestAnimationFrame(flush);
    }
  }

  schedule.flush = () => {
    if (frameId) {
      cancelAnimationFrame(frameId);
      frameId = 0;
    }
    flush();
  };

  return schedule;
}

function setupSmoothRange(rangeInput, onValue, onCommit) {
  let activePointerId = null;
  let dragging = false;
  let startX = 0;
  const dragThreshold = 3;
  const thumbHitSlop = 20;

  function updateValue(value) {
    const normalized = normalizeRangeValue(rangeInput, value);
    if (Number(rangeInput.value) !== normalized) {
      rangeInput.value = String(normalized);
      onValue(normalized);
    }
  }

  function cleanupPointer(event) {
    if (activePointerId === null || event.pointerId !== activePointerId) {
      return;
    }
    if (dragging) {
      updateValue(rangeValueFromClientX(rangeInput, event.clientX));
      onCommit(Number(rangeInput.value));
    }
    if (rangeInput.hasPointerCapture && rangeInput.hasPointerCapture(activePointerId)) {
      rangeInput.releasePointerCapture(activePointerId);
    }
    activePointerId = null;
    dragging = false;
    appState.isDraggingRange = false;
    refreshFromBridge();
  }

  rangeInput.addEventListener("pointerdown", (event) => {
    activePointerId = event.pointerId;
    startX = event.clientX;
    dragging = Math.abs(event.clientX - thumbCenterForRange(rangeInput)) <= thumbHitSlop;
    appState.isDraggingRange = true;
    event.preventDefault();
    rangeInput.focus();
    if (rangeInput.setPointerCapture) {
      rangeInput.setPointerCapture(activePointerId);
    }
  }, { passive: false });

  rangeInput.addEventListener("pointermove", (event) => {
    if (activePointerId === null || event.pointerId !== activePointerId) {
      return;
    }
    if (!dragging && Math.abs(event.clientX - startX) < dragThreshold) {
      return;
    }
    dragging = true;
    event.preventDefault();
    updateValue(rangeValueFromClientX(rangeInput, event.clientX));
  }, { passive: false });

  rangeInput.addEventListener("pointerup", cleanupPointer);
  rangeInput.addEventListener("pointercancel", cleanupPointer);
  rangeInput.addEventListener("click", (event) => event.preventDefault());
  rangeInput.addEventListener("input", () => onValue(Number(rangeInput.value)));
}

function renderMaterials() {
  const container = byId("materialList");
  container.innerHTML = "";
  STATES.forEach(({ state }) => {
    const item = appState.states[state];
    const card = document.createElement("article");
    card.className = "material-card";
    card.innerHTML = `
      <div class="material-header">
        <div class="thumb">MP4</div>
        <div class="material-title">
          <div class="material-name">${item.title}</div>
          <div class="material-file" data-role="material-name">${item.materialName}</div>
        </div>
      </div>
      <div class="status" data-role="material-status">${item.status}</div>
      <div class="control-row">
        <label>大小</label>
        <input data-role="scale" type="range" min="0" max="250" value="${item.scalePercent}" />
        <span class="metric" data-role="scale-value">${item.scalePercent}</span>
      </div>
      <div class="control-row">
        <label>速度</label>
        <input data-role="speed" type="range" min="25" max="300" value="${item.speedPercent}" />
        <span class="metric" data-role="speed-value">${item.speedPercent}</span>
      </div>
      <div class="control-row">
        <label>循环方式</label>
        <select data-role="loop">
          <option value="loop">循环播放</option>
          <option value="once">单次定格</option>
        </select>
        <span></span>
      </div>
      <div class="material-actions">
        <button class="primary-button" data-action="upload" type="button">上传 MP4</button>
        <button class="light-button" data-action="switch" type="button">切换动作</button>
        <button class="ghost-button" data-action="reset" type="button">解绑素材</button>
      </div>
    `;

    const loop = card.querySelector('[data-role="loop"]');
    const scaleInput = card.querySelector('[data-role="scale"]');
    const speedInput = card.querySelector('[data-role="speed"]');
    const scaleValue = card.querySelector('[data-role="scale-value"]');
    const speedValue = card.querySelector('[data-role="speed-value"]');
    const scheduleScale = createBridgeScheduler("setStateScale", state);
    const scheduleSpeed = createBridgeScheduler("setStateSpeed", state);
    loop.value = item.loopMode;
    setupSmoothRange(scaleInput, (value) => {
      item.scalePercent = value;
      scaleValue.textContent = value;
      scheduleScale(value);
    }, scheduleScale.flush);
    setupSmoothRange(speedInput, (value) => {
      item.speedPercent = value;
      speedValue.textContent = value;
      scheduleSpeed(value);
    }, scheduleSpeed.flush);
    loop.addEventListener("change", (event) => callBridge("setStateLoopMode", state, event.target.value));
    card.querySelector('[data-action="upload"]').addEventListener("click", () => callBridge("chooseStateVideo", state));
    card.querySelector('[data-action="switch"]').addEventListener("click", () => callBridge("requestState", state));
    card.querySelector('[data-action="reset"]').addEventListener("click", () => callBridge("resetStateVideo", state));
    container.appendChild(card);
  });
}

function renderActions() {
  const grid = byId("actionGrid");
  grid.innerHTML = "";
  appState.actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action.label;
    button.className = action.role === "orangeButton" ? "primary-button" : action.role === "dangerButton" ? "ghost-button" : "light-button";
    button.addEventListener("click", () => callBridge("requestState", action.state));
    grid.appendChild(button);
  });
}

function renderPreview() {
  const image = byId("previewImage");
  const message = byId("previewMessage");
  byId("previewFrameLabel").textContent = appState.preview.frameLabel || "当前帧：0 / 0";
  byId("previewMeta").textContent = appState.preview.playing ? "预览播放中" : "预览已暂停";
  byId("previewState").textContent = appState.preview.state ? appState.states[appState.preview.state]?.title || appState.preview.state : "未选择";
  if (appState.preview.image) {
    image.src = appState.preview.image;
    image.hidden = false;
    message.hidden = true;
  } else {
    image.hidden = true;
    message.hidden = false;
    message.textContent = appState.preview.message || "上传素材后显示首帧预览";
  }
}

function render() {
  byId("statusBar").textContent = appState.status;
  byId("blackBackgroundToggle").checked = Boolean(appState.blackBackground);
  renderMaterials();
  renderActions();
  renderPreview();
}

function applyPatch(payload) {
  if (typeof payload.revision === "number") {
    if (payload.revision === appState.revision) {
      return;
    }
    appState.revision = payload.revision;
  }
  if (payload.states) {
    Object.entries(payload.states).forEach(([state, value]) => {
      appState.states[state] = { ...appState.states[state], ...value };
    });
  }
  if (payload.actions) appState.actions = payload.actions;
  if (typeof payload.blackBackground === "boolean") appState.blackBackground = payload.blackBackground;
  if (payload.status) appState.status = payload.status;
  if (payload.preview) appState.preview = { ...appState.preview, ...payload.preview };
  render();
}

function setupControls() {
  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.addEventListener("click", () => applyTheme(button.dataset.themeOption));
  });
  byId("blackBackgroundToggle").addEventListener("change", (event) => {
    callBridge("setBlackBackground", event.target.checked);
  });
  byId("sayButton").addEventListener("click", () => callBridge("say", byId("dialogueInput").value.trim()));
  byId("chatButton").addEventListener("click", () => callBridge("chat", byId("dialogueInput").value.trim()));
  byId("playPreviewButton").addEventListener("click", () => callBridge("playPreview"));
  byId("pausePreviewButton").addEventListener("click", () => callBridge("pausePreview"));
  byId("syncPreviewButton").addEventListener("click", () => callBridge("syncPreview"));
  byId("quitButton").addEventListener("click", () => callBridge("quitApp"));
}

window.desktopPetControl = { applyPatch };
applyTheme(appState.theme, false);
setupControls();
render();

function connectElectronBridge() {
  appState.bridge = window.desktopPetApi;
  byId("connectionStatus").textContent = "已连接本地控制台";
  refreshFromBridge();
  window.setInterval(refreshFromBridge, 800);
}

if (window.desktopPetApi) {
  connectElectronBridge();
} else if (window.qt && window.QWebChannel) {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    appState.bridge = channel.objects.bridge;
    byId("connectionStatus").textContent = "已连接 Python";
    refreshFromBridge();
  });
} else {
  byId("connectionStatus").textContent = "浏览器预览模式";
}
