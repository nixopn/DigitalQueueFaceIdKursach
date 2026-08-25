import { api, listenState, nav } from "./api.js";

document.getElementById("nav").outerHTML = nav("/admin.html");
const list = document.getElementById("list");
const hw = document.getElementById("hw");

function render(state) {
  const queue = state.queue || [];
  hw.textContent = JSON.stringify(state.hardware || {}, null, 2);
  if (state.hardware?.camera_backend) {
    document.getElementById("backend").value = state.hardware.camera_backend === "opencv" || state.hardware.camera_backend === "v4l2"
      ? state.hardware.camera_backend
      : "browser";
    document.getElementById("device").value = state.hardware.camera_device || "0";
  }
  if (!queue.length) {
    list.innerHTML = `<p class="muted">Нет активных клиентов</p>`;
    return;
  }
  list.innerHTML = queue.map((q) => `<div class="card" style="margin-bottom:10px;padding:12px">
    <strong>№ ${q.queue_number}</strong> · клиент #${q.client_id}
    <div class="muted">${(q.items || []).map((i) => i.name).join(", ") || "без заказа"}</div>
    <div class="row" style="margin-top:8px">
      <button data-serve="${q.id}" class="ok">Обслужен</button>
      <button data-remove="${q.id}" class="secondary">Удалить</button>
    </div>
  </div>`).join("");
}

list.addEventListener("click", async (ev) => {
  const serve = ev.target.dataset.serve;
  const remove = ev.target.dataset.remove;
  if (serve) await api("/api/queue/serve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ queue_id: Number(serve) }) });
  if (remove) await api("/api/queue/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ queue_id: Number(remove) }) });
});

document.getElementById("reset").onclick = async () => {
  if (confirm("Сбросить активную очередь?")) {
    await api("/api/queue/reset", { method: "POST" });
  }
};

document.getElementById("applyCam").onclick = async () => {
  await api("/api/camera", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      backend: document.getElementById("backend").value,
      device: document.getElementById("device").value || "0",
    }),
  });
};

listenState(render);
