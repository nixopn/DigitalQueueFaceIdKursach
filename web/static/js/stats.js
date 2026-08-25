import { listenState, nav } from "./api.js";

document.getElementById("nav").outerHTML = nav("/stats.html");

function render(state) {
  const s = state.stats || {};
  document.getElementById("summary").innerHTML = `
    <p>Клиентов в базе: <strong>${s.clients || 0}</strong></p>
    <p>Ждут: <strong>${s.waiting || 0}</strong> · обслуживаются: <strong>${s.serving || 0}</strong></p>
    <p>Обслужено: <strong>${s.done || 0}</strong> · заказов: <strong>${s.orders || 0}</strong></p>
  `;
  const hourly = state.hourly || [];
  const max = Math.max(1, ...hourly.map((h) => h.count));
  document.getElementById("chart").innerHTML = hourly.length
    ? hourly.map((h) => `<div class="bar" title="${h.hour}:00 — ${h.count}" style="height:${Math.round((h.count / max) * 150)}px"></div>`).join("")
    : `<p class="muted">Пока нет данных</p>`;
  document.getElementById("events").innerHTML = (state.events || []).map((e) =>
    `<div class="muted">${e.created_at} · ${e.kind}<br>${e.payload}</div>`
  ).join("") || `<p class="muted">Событий нет</p>`;
}

listenState(render);
