export async function api(path, options = {}) {
  const res = await fetch(path, options);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok) {
    let msg = res.statusText;
    if (data) {
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
      else msg = data.error || data.message || msg;
    }
    throw new Error(msg);
  }
  return data;
}

export function listenState(onData) {
  const es = new EventSource("/api/events");
  es.onmessage = (ev) => {
    try { onData(JSON.parse(ev.data)); } catch {}
  };
  return es;
}

export function nav(active) {
  const items = [
    ["/", "Терминал"],
    ["/monitor.html", "Монитор"],
    ["/admin.html", "Админ"],
    ["/stats.html", "Статистика"],
  ];
  return `<nav class="nav">
    <div class="nav-title">Очередь</div>
    ${items.map(([href, label]) => `<a href="${href}" class="${href === active ? "active" : ""}">${label}</a>`).join("")}
  </nav>`;
}
