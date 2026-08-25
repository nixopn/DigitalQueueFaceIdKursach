import { listenState, nav } from "./api.js";

document.getElementById("nav").outerHTML = nav("/monitor.html");
const rows = document.getElementById("rows");
const updated = document.getElementById("updated");

function render(state) {
  updated.textContent = "Обновлено: " + (state.updated_at || "");
  const queue = state.queue || [];
  if (!queue.length) {
    rows.innerHTML = `<tr><td colspan="5" class="muted">Очередь пуста</td></tr>`;
    return;
  }
  rows.innerHTML = queue.map((q) => `<tr>
    <td class="ticket" style="font-size:22px">${q.queue_number}</td>
    <td>#${q.client_id}</td>
    <td><span class="badge">${q.status}</span></td>
    <td>${(q.items || []).map((i) => i.name + (i.qty ? "×" + i.qty : "")).join(", ") || "—"}</td>
    <td>${q.created_at}</td>
  </tr>`).join("");
}

listenState(render);
