import { api, listenState, nav } from "./api.js";

document.getElementById("nav").outerHTML = nav("/");

const video = document.getElementById("video");
const shot = document.getElementById("shot");
const devicesSel = document.getElementById("devices");
const sourceSel = document.getElementById("source");
const resultEl = document.getElementById("result");
const ticketEl = document.getElementById("ticket");
const metaEl = document.getElementById("meta");
const catalogEl = document.getElementById("catalog");
const catalogWrap = document.getElementById("catalogWrap");

let stream = null;
let catalog = [];
let cart = new Map();

async function listCameras() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const cams = devices.filter((d) => d.kind === "videoinput");
  devicesSel.innerHTML = cams.map((d, i) =>
    `<option value="${d.deviceId}">${d.label || "Камера " + (i + 1)}</option>`
  ).join("");
}

async function startBrowserCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  const deviceId = devicesSel.value;
  const constraints = deviceId
    ? { video: { deviceId: { exact: deviceId }, width: 640, height: 480 } }
    : { video: { facingMode: "user", width: 640, height: 480 } };
  stream = await navigator.mediaDevices.getUserMedia(constraints);
  video.srcObject = stream;
  video.hidden = false;
  shot.hidden = true;
  await listCameras();
}

function captureBlob() {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext("2d").drawImage(video, 0, 0);
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.9));
}

function showResult(data) {
  resultEl.textContent = data.message || data.reason || "Готово";
  ticketEl.textContent = data.ok ? data.queue_number : "—";
  metaEl.textContent = data.ok
    ? `${data.registered ? "Новый клиент" : "Узнан"} · совпадение ${data.score} · впереди ${data.ahead}`
    : "";
  if (data.preview_base64) {
    shot.src = "data:image/jpeg;base64," + data.preview_base64;
    shot.hidden = false;
    video.hidden = sourceSel.value !== "browser";
  }
}

async function recognize() {
  resultEl.textContent = "Сканирование…";
  try {
    let data;
    if (sourceSel.value === "device") {
      data = await api("/api/recognize/device", { method: "POST" });
    } else {
      const blob = await captureBlob();
      const fd = new FormData();
      fd.append("file", blob, "frame.jpg");
      data = await api("/api/recognize", { method: "POST", body: fd });
    }
    showResult(data);
  } catch (err) {
    resultEl.textContent = err.message;
  }
}

function renderCatalog() {
  catalogEl.innerHTML = catalog.map((item) => {
    const on = cart.has(item.id);
    const count = cart.get(item.id)?.qty || 0;
    return `<div class="item ${on ? "on" : ""}" data-id="${item.id}">
      <strong>${item.name}</strong>
      <div class="muted">${item.price} ₽${count ? " × " + count : ""}</div>
    </div>`;
  }).join("");
}

catalogEl.addEventListener("click", (ev) => {
  const node = ev.target.closest(".item");
  if (!node) return;
  const item = catalog.find((x) => x.id === node.dataset.id);
  const prev = cart.get(item.id);
  cart.set(item.id, { ...item, qty: (prev?.qty || 0) + 1 });
  renderCatalog();
});

document.getElementById("recognize").onclick = recognize;
document.getElementById("preorder").onclick = () => {
  catalogWrap.hidden = !catalogWrap.hidden;
};
document.getElementById("saveCart").onclick = async () => {
  const items = [...cart.values()];
  await api("/api/cart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  resultEl.textContent = items.length
    ? "Предзаказ сохранён. Нажмите «Распознавание»."
    : "Корзина пуста";
};
document.getElementById("clearCart").onclick = () => {
  cart.clear();
  renderCatalog();
};
document.getElementById("enableCam").onclick = startBrowserCamera;
sourceSel.onchange = async () => {
  if (sourceSel.value === "browser") await startBrowserCamera();
  else {
    if (stream) stream.getTracks().forEach((t) => t.stop());
    video.hidden = true;
    resultEl.textContent = "Кадр будет взят с OpenCV/V4L2 на плате или с USB, указанной в настройках.";
  }
};
devicesSel.onchange = startBrowserCamera;

listenState((state) => {
  if (state.pending_cart?.length && cart.size === 0) {
    state.pending_cart.forEach((item) => cart.set(item.id, item));
    renderCatalog();
  }
});

const boot = async () => {
  catalog = await api("/api/catalog");
  renderCatalog();
  try {
    await startBrowserCamera();
    await listCameras();
  } catch (err) {
    resultEl.textContent = "Нет доступа к камере браузера: " + err.message;
  }
};
boot();
