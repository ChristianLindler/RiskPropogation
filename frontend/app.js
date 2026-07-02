const $ = (id) => document.getElementById(id);

let graph = null;
let activeWl = null;
let unseen = new Set();
let notifications = [];
let panelOpen = false;
let sse = null;

const wlNav = $("wl-nav");
const main = $("main-panel");
const notifBtn = $("notif-btn");
const notifBadge = $("notif-badge");
const notifPanel = $("notif-panel");
const notifList = $("notif-list");

const pct = (n) => `${Math.round((n || 0) * 100)}%`;
const entity = (id) => graph?.entities?.find((e) => e.id === id);
const watchlist = (id) => graph?.watchlists?.find((w) => w.id === id);

async function loadGraph() {
  const res = await fetch("/graph", { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /graph returned ${res.status}`);
  graph = await res.json();
}

function renderNotifs() {
  const unread = notifications.filter((n) => !n.read).length;
  notifBtn.classList.toggle("has-unread", unread > 0);
  notifBadge.classList.toggle("visible", unread > 0);
  notifBadge.textContent = unread > 9 ? "9+" : String(unread);

  if (!notifications.length) {
    notifList.innerHTML = `<div class="notif-empty">No alerts yet</div>`;
    return;
  }

  notifList.innerHTML = notifications
    .map((n, i) => {
      const a = n.alert;
      return `
        <div class="notif-item ${n.read ? "" : "unread"}" data-i="${i}">
          <div class="notif-item-why">${a.cause.summary}</div>
          <div class="notif-item-title">${a.entity_name}
            <span class="delta">+${Math.round(a.delta * 100)}%</span>
          </div>
          <div class="notif-item-change">
            ${pct(a.old_risk)} → ${pct(a.new_risk)}
            <span class="muted"> · ${a.old_band} → ${a.new_band}</span>
          </div>
          <div class="notif-item-why">${a.cause.summary}</div>
          <div class="notif-item-meta">${a.watchlist_name}</div>
        </div>`;
    })
    .join("");

  notifList.querySelectorAll(".notif-item").forEach((el) => {
    el.onclick = () => {
      const n = notifications[+el.dataset.i];
      n.read = true;
      goTo(n.alert);
      renderNotifs();
    };
  });
}

function goTo(alert) {
  activeWl = alert.watchlist_id;
  unseen.delete(activeWl);
  panelOpen = false;
  notifPanel.classList.remove("open");
  notifBtn.classList.remove("open");
  render();
}

function render() {
  renderSidebar();
  renderMain();
}

function renderSidebar() {
  wlNav.innerHTML = graph.watchlists
    .map((wl) => {
      const cls = [
        wl.id === activeWl ? "active" : "",
        unseen.has(wl.id) && wl.id !== activeWl ? "has-unseen" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `<li class="wl-nav-item ${cls}" data-id="${wl.id}">
        <span class="wl-name">${wl.name}</span>
        <span class="wl-alert-dot"></span>
      </li>`;
    })
    .join("");

  wlNav.querySelectorAll(".wl-nav-item").forEach((el) => {
    el.onclick = () => {
      activeWl = el.dataset.id;
      unseen.delete(activeWl);
      render();
    };
  });
}

function renderMain() {
  const wl = watchlist(activeWl);
  if (!wl) {
    main.innerHTML = `<div class="empty-state">Select a watchlist</div>`;
    return;
  }

  const rows = wl.entities
    .map((id) => entity(id))
    .filter(Boolean)
    .map(
      (e) => `
      <div class="entity-row" data-id="${e.id}">
        <span class="name">${e.name}</span>
        <span class="meta">${[e.attributes?.type, e.attributes?.role || e.attributes?.seniority].filter(Boolean).join(" · ")}</span>
        <span class="score"><span class="band-dot ${e.band || "low"}"></span>${pct(e.current_risk)}</span>
      </div>`
    )
    .join("");

  main.innerHTML = `
    <div class="detail-title-row">
      <h1 class="detail-title">${wl.name}</h1>
      <span class="entity-count-badge"><span class="band-dot"></span>${wl.entities.length} tracked</span>
    </div>
    <div class="entity-rows">${rows}</div>
    <div class="section-label">Description</div>
    <p class="detail-desc">${wl.description}</p>`;
}

function onAlert(alert) {
  const e = entity(alert.entity_id);
  if (e) {
    e.current_risk = alert.new_risk;
    e.band = alert.new_band;
  }

  unseen.add(alert.watchlist_id);
  if (alert.watchlist_id === activeWl) unseen.delete(alert.watchlist_id);

  notifications.unshift({ alert, read: false });
  renderNotifs();
  render();

  if (alert.watchlist_id === activeWl) {
    requestAnimationFrame(() => {
      main.querySelector(`[data-id="${alert.entity_id}"]`)?.classList.add("flash");
    });
  }
}

$("notif-btn").onclick = (e) => {
  e.stopPropagation();
  panelOpen = !panelOpen;
  notifPanel.classList.toggle("open", panelOpen);
  notifBtn.classList.toggle("open", panelOpen);
  if (panelOpen) {
    notifications.forEach((n) => (n.read = true));
    renderNotifs();
  }
};

$("notif-clear").onclick = (e) => {
  e.stopPropagation();
  notifications = [];
  unseen.clear();
  renderNotifs();
  render();
};

document.onclick = (e) => {
  if (!e.target.closest(".notif-wrap")) {
    panelOpen = false;
    notifPanel.classList.remove("open");
    notifBtn.classList.remove("open");
  }
};

async function init() {
  try {
    await loadGraph();
    if (!graph.watchlists?.length) throw new Error("No watchlists in /graph");
    activeWl = graph.watchlists[0].id;
    renderNotifs();
    render();
    sse = new EventSource("/events");
    sse.onmessage = (ev) => onAlert(JSON.parse(ev.data));
  } catch (err) {
    main.innerHTML = `<div class="empty-state">
      <p>Server not running.</p>
      <p class="hint">Run <code>uvicorn backend.main:app --reload</code> then open <strong>http://localhost:8000</strong></p>
    </div>`;
    console.error(err);
  }
}

init();
