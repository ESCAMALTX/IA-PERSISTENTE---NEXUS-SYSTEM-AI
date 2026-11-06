/* NEXUS SYSTEM AI - dashboard */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const MAX_LOG_LINES = 600;

  const state = {
    conversationId: null,
    logs: [],
    history: [],
    logFilter: "",
  };

  const fmtTime = (ts) => new Date(ts).toLocaleTimeString("es-ES", { hour12: false });
  const fmtDate = (iso) => new Date(iso).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
  const clamp = (n) => Math.max(0, Math.min(100, n));

  function toast(message, isError = false) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.toggle("error", isError);
    el.classList.add("show");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("show"), 4200);
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      let detail = `Error ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
      throw new Error(detail);
    }
    return res.json();
  }

  /* ------------------------------ navegación ------------------------------ */
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      $(`#view-${btn.dataset.view}`).classList.add("active");
      if (btn.dataset.view === "memory") loadMemory();
      if (btn.dataset.view === "incidents") loadIncidents();
    });
  });

  /* ------------------------------ métricas ------------------------------ */
  function setGauge(barId, valId, value, thresholds) {
    const bar = $(barId);
    $(valId).textContent = `${value.toFixed(1)}%`;
    bar.style.width = `${clamp(value)}%`;
    bar.classList.toggle("warn", value >= thresholds.cpu * 0.85 && value < thresholds.cpu);
    bar.classList.toggle("danger", value >= thresholds.cpu);
  }

  function renderMetrics(snap, thresholds) {
    if (!snap) return;
    setGauge("#cpuBar", "#cpuVal", snap.cpu_percent, { cpu: thresholds.cpu });
    setGauge("#ramBar", "#ramVal", snap.ram_percent, { cpu: thresholds.ram });
    setGauge("#diskBar", "#diskVal", snap.disk_percent, { cpu: thresholds.disk });

    $("#ramDetail").textContent = `${snap.ram_used_gb} / ${snap.ram_total_gb} GB en uso`;
    $("#diskDetail").textContent = `${snap.disk_used_gb} / ${snap.disk_total_gb} GB en uso`;
    $("#kProc").textContent = snap.processes;
    $("#kCores").textContent = snap.cpu_cores;
    $("#kUptime").textContent = `${snap.uptime_hours} h`;
    $("#kNet").textContent = `${snap.net_recv_mb} MB / ${snap.net_sent_mb} MB`;
  }

  function drawSpark(canvasId, values, color) {
    const canvas = $(canvasId);
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight || 46;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    if (values.length < 2) return;
    const max = 100;
    const stepX = w / (values.length - 1);
    const y = (v) => h - (clamp(v) / max) * (h - 4) - 2;

    ctx.beginPath();
    values.forEach((v, i) => {
      const px = i * stepX;
      const py = y(v);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.stroke();

    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, `${color}55`);
    grad.addColorStop(1, "transparent");
    ctx.fillStyle = grad;
    ctx.fill();
  }

  function renderSparks(history) {
    const cpus = history.map((h) => h.cpu_percent);
    const rams = history.map((h) => h.ram_percent);
    drawSpark("#cpuSpark", cpus, "#21e6c1");
    drawSpark("#ramSpark", rams, "#3b82f6");
  }

  function renderProcesses(procs) {
    const body = $("#procTable tbody");
    body.innerHTML = procs.map((p) => `
      <tr>
        <td>${escapeHtml(p.name || "?")}</td>
        <td class="muted">${p.pid}</td>
        <td>${p.cpu_percent.toFixed(1)}%</td>
        <td>${p.memory_percent.toFixed(1)}%</td>
      </tr>`).join("") || `<tr><td colspan="4" class="muted">Sin datos</td></tr>`;
  }

  async function loadMetrics() {
    try {
      const data = await api("/api/metrics");
      state.history = data.history;
      renderSparks(state.history);
      renderProcesses(data.top_processes);
    } catch { /* silencioso */ }
  }

  /* ------------------------------ estado ------------------------------ */
  async function loadStatus() {
    try {
      const s = await api("/api/status");
      renderMetrics(s.metrics, s.thresholds);
      renderSparks(Object.keys(state).length ? state.history : []);

      const badge = $("#overallBadge");
      badge.textContent = s.overall === "ok" ? "Operativo" : "Requiere atención";
      badge.className = `badge ${s.overall === "ok" ? "ok" : "warn"}`;

      $("#agentList").innerHTML = s.agents.map((a) => `
        <div class="agent ${a.state === "online" ? "" : "off"}">
          <i></i><b>${escapeHtml(a.name)}</b>
        </div>`).join("");

      if (!s.ai_configured) {
        toast("DEEPSEEK_API_KEY no configurada: la IA no responderá hasta crear .env");
      }
    } catch (e) {
      console.error(e);
    }
  }

  /* ------------------------------ logs ------------------------------ */
  function logLine(entry) {
    return `<div class="log-line" data-level="${escapeHtml(entry.level)}">
      <span class="t">${fmtTime(entry.created_at)}</span>
      <span class="lv ${escapeHtml(entry.level)}">${escapeHtml(entry.level)}</span>
      <span class="src">[${escapeHtml(entry.source)}]</span>
      <span class="m">${escapeHtml(entry.message)}</span>
    </div>`;
  }

  function appendLog(entry) {
    state.logs.push(entry);
    if (state.logs.length > MAX_LOG_LINES) state.logs.shift();
    if (state.logFilter && entry.level !== state.logFilter) return;
    const box = $("#logBox");
    const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
    box.insertAdjacentHTML("beforeend", logLine(entry));
    while (box.children.length > MAX_LOG_LINES) box.removeChild(box.firstChild);
    if (atBottom) box.scrollTop = box.scrollHeight;
  }

  function renderLogs() {
    const filtered = state.logFilter
      ? state.logs.filter((l) => l.level === state.logFilter)
      : state.logs;
    const box = $("#logBox");
    box.innerHTML = filtered.map(logLine).join("");
    box.scrollTop = box.scrollHeight;
  }

  $("#logFilter").addEventListener("change", (e) => {
    state.logFilter = e.target.value;
    renderLogs();
  });
  $("#btnClearLogs").addEventListener("click", () => {
    state.logs = [];
    renderLogs();
  });

  /* ------------------------------ alertas / incidentes ------------------------------ */
  function incidentCard(inc, { inPanel = false } = {}) {
    const severityClass = inc.severity === "info" ? "info" : inc.severity;
    const statusClass = inc.status === "resolved" ? "resolved" : "";
    const diagnosis = inc.diagnosis
      ? `<div class="diag">${escapeHtml(inc.diagnosis)}</div>`
      : "";
    return `<article class="incident ${severityClass} ${statusClass}" data-id="${inc.id}">
      <header>
        <span><b>${escapeHtml(inc.kind.toUpperCase())}</b> · ${escapeHtml(inc.message)}</span>
        <time>${fmtDate(inc.created_at)}</time>
      </header>
      ${inPanel ? "" : `<div class="muted" style="font-size:11.5px">Estado: ${inc.status === "open" ? "abierto" : "resuelto"}</div>`}
      ${diagnosis}
      ${inPanel ? "" : `<div class="incident-actions">
        <button class="btn small" data-action="diagnose" data-id="${inc.id}">Diagnosticar</button>
        ${inc.status === "open" ? `<button class="btn small danger" data-action="resolve" data-id="${inc.id}">Resolver</button>` : ""}
      </div>`}
    </article>`;
  }

  async function loadAlerts() {
    try {
      const items = await api("/api/incidents?limit=20");
      // Primero los abiertos, luego los resueltos más recientes.
      const sorted = items.sort((a, b) =>
        (a.status === "open" ? 0 : 1) - (b.status === "open" ? 0 : 1) || b.id - a.id
      ).slice(0, 6);
      const box = $("#alertList");
      box.innerHTML = sorted.length
        ? sorted.map((i) => incidentCard(i, { inPanel: true })).join("")
        : `<p class="muted">Sin alertas.</p>`;
    } catch { /* silencioso */ }
  }

  async function loadIncidents() {
    try {
      const items = await api("/api/incidents?limit=100");
      const box = $("#incidentList");
      box.innerHTML = items.length
        ? items.map((i) => incidentCard(i)).join("")
        : `<p class="muted">Sin incidentes registrados.</p>`;
    } catch (e) {
      toast(e.message, true);
    }
  }

  $("#incidentList").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = btn.dataset.id;
    btn.disabled = true;
    try {
      if (btn.dataset.action === "diagnose") {
        const data = await api(`/api/incidents/${id}/diagnose`, { method: "POST" });
        const card = document.querySelector(`.incident[data-id="${id}"]`);
        if (card && !card.querySelector(".diag")) {
          card.insertAdjacentHTML("beforeend", `<div class="diag">${escapeHtml(data.diagnosis)}</div>`);
        }
      } else {
        await api(`/api/incidents/${id}/resolve`, { method: "POST" });
        loadIncidents();
        loadAlerts();
      }
    } catch (err) {
      toast(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  /* ------------------------------ análisis IA ------------------------------ */
  $("#btnAnalyze").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = "Analizando…";
    try {
      const data = await api("/api/analyze", { method: "POST" });
      toast(data.analysis);
      loadAlerts();
    } catch (err) {
      toast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "Analizar con IA";
    }
  });

  /* ------------------------------ memoria ------------------------------ */
  async function loadMemory() {
    try {
      const [status, convs] = await Promise.all([
        api("/api/status"),
        api("/api/conversations"),
      ]);
      $("#mConv").textContent = status.memory.conversations;
      $("#mMsg").textContent = status.memory.messages;
      $("#mInc").textContent = status.memory.incidents;
      $("#mOpen").textContent = status.memory.open_incidents;
      $("#mLogs").textContent = status.memory.logs;

      const body = $("#convTable tbody");
      body.innerHTML = convs.conversations.map((c) => `
        <tr>
          <td>${escapeHtml(c.title || "Sin título")}</td>
          <td>${c.message_count}</td>
          <td class="muted">${fmtDate(c.created_at)}</td>
          <td class="muted">${fmtDate(c.updated_at)}</td>
          <td><button class="btn small" data-conv="${c.id}">Abrir</button>
              <button class="btn small danger" data-del="${c.id}">Eliminar</button></td>
        </tr>`).join("") || `<tr><td colspan="5" class="muted">Sin conversaciones</td></tr>`;
    } catch (e) {
      toast(e.message, true);
    }
  }

  $("#convTable").addEventListener("click", async (e) => {
    const openBtn = e.target.closest("button[data-conv]");
    const delBtn = e.target.closest("button[data-del]");
    if (openBtn) {
      const id = Number(openBtn.dataset.conv);
      document.querySelector('.nav-item[data-view="chat"]').click();
      await openConversation(id);
    } else if (delBtn) {
      const id = Number(delBtn.dataset.del);
      try {
        await api(`/api/conversations/${id}`, { method: "DELETE" });
        if (state.conversationId === id) {
          state.conversationId = null;
          $("#messages").innerHTML = "";
        }
        await loadConversations();
        loadMemory();
      } catch (err) {
        toast(err.message, true);
      }
    }
  });

  /* ------------------------------ chat ------------------------------ */
  function renderMessage(role, content) {
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;
    row.innerHTML = `<div class="avatar">${role === "user" ? "TÚ" : "AI"}</div>
      <div class="bubble">${escapeHtml(content)}</div>`;
    $("#messages").appendChild(row);
    $("#messages").scrollTop = $("#messages").scrollHeight;
    return row;
  }

  async function loadConversations() {
    try {
      const data = await api("/api/conversations");
      const select = $("#convSelect");
      select.innerHTML = `<option value="">Nueva conversación</option>` +
        data.conversations.map((c) =>
          `<option value="${c.id}">${escapeHtml((c.title || "Sin título").slice(0, 50))}</option>`
        ).join("");

      if (state.conversationId) select.value = String(state.conversationId);
      return data;
    } catch {
      return null;
    }
  }

  async function openConversation(id) {
    try {
      const data = await api(`/api/conversations/${id}`);
      state.conversationId = id;
      $("#convSelect").value = String(id);
      $("#messages").innerHTML = "";
      data.messages.forEach((m) => renderMessage(m.role, m.content));
    } catch (e) {
      toast(e.message, true);
    }
  }

  $("#convSelect").addEventListener("change", (e) => {
    const id = Number(e.target.value);
    if (id) openConversation(id);
    else {
      state.conversationId = null;
      $("#messages").innerHTML = "";
    }
  });

  $("#btnNewConv").addEventListener("click", () => {
    state.conversationId = null;
    $("#convSelect").value = "";
    $("#messages").innerHTML = "";
    $("#chatInput").focus();
  });

  $("#chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      $("#chatForm").requestSubmit();
    }
  });

  $("#chatForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#chatInput");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    renderMessage("user", text);
    const typing = renderMessage("assistant", "pensando…");
    typing.querySelector(".bubble").classList.add("typing");
    const sendBtn = $("#btnSend");
    sendBtn.disabled = true;

    try {
      const data = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
      });
      state.conversationId = data.conversation_id;
      typing.querySelector(".bubble").classList.remove("typing");
      typing.querySelector(".bubble").textContent = data.reply;
      $("#messages").scrollTop = $("#messages").scrollHeight;
      await loadConversations();
    } catch (err) {
      typing.remove();
      toast(err.message, true);
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  });

  /* ------------------------------ websocket ------------------------------ */
  let ws = null;
  let reconnectTimer = null;

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => {
      const conn = $("#connState");
      conn.className = "conn online";
      conn.innerHTML = `<span class="dot"></span> en vivo`;
      clearTimeout(reconnectTimer);
    };

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }

      switch (msg.type) {
        case "init": {
          state.logs = [];
          $("#logBox").innerHTML = "";
          (msg.data.logs || []).forEach(appendLog);
          renderLogs();
          state.history = msg.data.history || [];
          renderSparks(state.history);
          renderMetrics(msg.data.metrics, { cpu: 85, ram: 85, disk: 90 });
          loadStatus();
          break;
        }
        case "metrics": {
          state.history.push(msg.data);
          if (state.history.length > 120) state.history.shift();
          renderSparks(state.history);
          renderMetrics(msg.data, { cpu: 85, ram: 85, disk: 90 });
          break;
        }
        case "log":
          appendLog(msg.data);
          break;
        case "incident":
          loadAlerts();
          if ($("#view-incidents").classList.contains("active")) loadIncidents();
          loadStatus();
          break;
        case "incident_resolved":
          loadAlerts();
          break;
        case "diagnosis": {
          const card = document.querySelector(
            `.incident[data-id="${msg.data.id}"]:not([data-panel])`
          );
          if (card && !card.querySelector(".diag")) {
            card.insertAdjacentHTML("beforeend",
              `<div class="diag">${escapeHtml(msg.data.diagnosis)}</div>`);
          }
          loadAlerts();
          break;
        }
      }
    };

    ws.onclose = () => {
      const conn = $("#connState");
      conn.className = "conn offline";
      conn.innerHTML = `<span class="dot"></span> reconectando…`;
      reconnectTimer = setTimeout(connectWS, 3000);
    };

    ws.onerror = () => ws.close();
  }

  /* ------------------------------ utils ------------------------------ */
  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* ------------------------------ init ------------------------------ */
  async function init() {
    connectWS();
    await loadStatus();
    await loadMetrics();
    await loadAlerts();
    const data = await loadConversations();
    if (data && data.latest) {
      await openConversation(data.latest);
    }
    loadMemory();
  }

  init();
  setInterval(loadMetrics, 10000);
})();
