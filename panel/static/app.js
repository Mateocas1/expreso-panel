"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const body = document.body;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const plural = new Intl.PluralRules("es");
  const pl = (n, one, other) => (plural.select(n) === "one" ? one : other);

  // Server text is always set with textContent; innerHTML only ever receives these constants.
  const svg = (size, bold, paths) => `<svg class="ico${bold ? " b" : ""}" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">${paths}</svg>`;
  const PATHS = {
    ok: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    prev: '<path d="M3 12a9 9 0 1 0 3-6.7M3 4v4h4"/>',
    fix: '<rect x="2.5" y="6.5" width="19" height="11" rx="2"/><path d="M7 10v4"/>',
    none: '<path d="M7.5 18.5h9.25a4 4 0 0 0 .9-7.9 6 6 0 0 0-11.2-1.4 4.6 4.6 0 0 0 1.05 9.3z"/><path d="M3.5 3.5l17 17"/>',
  };
  const BOLD = { ok: false, prev: false, fix: true, none: true };
  const icon = (state, size = 16) => svg(size, BOLD[state], PATHS[state]);
  const CHEVRON = svg(12, false, '<path d="M9 6l6 6-6 6"/>');
  const UPLOAD = svg(16, false, '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>');
  const STATES = ["ok", "prev", "fix", "none"];
  const LEGEND = [["ok", "Cargado"], ["prev", "Ya estaba"], ["fix", "Para corregir"], ["none", "Sin respuesta"]];
  const FALLBACK = {
    headline: "El panel no responde.",
    sub: "No se cargó ningún envío. Probá de nuevo en unos minutos; si sigue igual, avisale a sistemas.",
    button: "Elegir otro archivo",
    action: "pick_other",
  };
  const OVERDUE_FALLBACK = {
    headline: "El panel no responde.",
    sub: "No se pudo consultar el estado de los envíos. Probá de nuevo en unos minutos; si sigue igual, avisale a sistemas.",
    button: "Volver a intentar",
    action: "retry",
  };
  const IDLE = "Elegí un envío para ver su estado.";

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  const final = $("final");
  const liveBox = document.querySelector(".answer .live");
  const legend = $("legend");
  const announce = $("announce");
  const mapEl = $("map");
  const picked = $("picked");
  const sheet = $("sheet");
  const fixesSection = $("para-corregir");
  const overview = $("overview");
  const fileInput = $("file");
  const drop = $("drop");
  const dropText = $("drop-text");
  const DROP_TEXT = dropText.textContent;

  const S = {
    exportId: null, preview: null, name: "", runId: null, es: null, busy: false,
    at: "", tiles: new Map(), byRemito: new Map(), seen: new Set(),
    counts: { ok: 0, prev: 0, fix: 0, none: 0 }, filled: 0, n: 0, selected: null,
  };

  // The run in progress (or the last export name, for the hint) survives a reload for as long as the tab does
  const memory = {
    read() { try { return JSON.parse(sessionStorage.getItem("expreso-panel")); } catch (_) { return null; } },
    write(value) {
      try {
        if (value) sessionStorage.setItem("expreso-panel", JSON.stringify(value)); else sessionStorage.removeItem("expreso-panel");
      } catch (_) { /* storage blocked: reloading just starts over */ }
    },
  };

  // ---- Small helpers ----------------------------------------------------------------------------

  async function api(path, opts) {
    try {
      const r = await fetch(path, opts);
      let data = null;
      try { data = await r.json(); } catch (_) { /* not JSON */ }
      return { ok: r.ok, status: r.status, data };
    } catch (_) {
      return { ok: false, status: 0, data: null };
    }
  }
  const answerOf = res => (res.data && res.data.answer) || FALLBACK;

  const setMeta = parts => {
    $("meta").replaceChildren(...parts.filter(Boolean).map(t => el("span", null, t)));
  };
  const timeLabel = iso => {
    let d = new Date(iso);
    if (!iso || isNaN(d)) d = new Date();
    const hm = d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });
    if (d.toDateString() === new Date().toDateString()) return `Carga de hoy, ${hm}`;
    return `Carga del ${d.toLocaleDateString("es-AR", { day: "numeric", month: "long" })}, ${hm}`;
  };
  const setTitle = t => { document.title = t ? `${t} · Expreso Andino` : "Envíos a Expreso Andino"; };
  const setView = v => {
    body.dataset.view = v;
    $("pick").hidden = v !== "pick";
    $("board").hidden = v === "pick" || v === "overdue";
    $("overdue").hidden = v !== "overdue";
    $("open-overdue").hidden = v !== "preview" && v !== "result";
  };
  const envios = n => `${n} ${pl(n, "envío", "envíos")}`;
  const closeStream = () => { if (S.es) { S.es.close(); S.es = null; } };

  // ---- Step 1: pick the export ------------------------------------------------------------------

  function showPick(hintName, focus) {
    closeStream();
    body.classList.remove("running");
    S.exportId = null;
    S.preview = null;
    memory.write(hintName ? { name: hintName } : null);
    setView("pick");
    setMeta([]);
    setTitle("");
    const hint = $("pick-hint");
    hint.hidden = !hintName;
    hint.textContent = hintName ? `La última vez cargaste «${hintName}».` : "";
    drop.classList.remove("busy", "over");
    dropText.textContent = DROP_TEXT;
    if (focus) fileInput.focus();
  }

  const headerSafe = name => name.replace(/[^\x20-\xff]/g, "_");

  async function handleFile(file) {
    if (!file || S.busy) return;
    S.busy = true;
    S.at = new Date().toISOString();
    drop.classList.remove("over");
    drop.classList.add("busy");
    dropText.textContent = `Leyendo «${file.name}»…`;
    const res = await api("/api/exports", { method: "POST", headers: { "X-Export-Name": headerSafe(file.name) }, body: file });
    S.busy = false;
    drop.classList.remove("busy");
    dropText.textContent = DROP_TEXT;
    S.name = file.name;
    if (res.status === 201 && res.data && res.data.preview) {
      S.exportId = res.data.export_id;
      S.preview = res.data.preview;
      S.name = S.preview.export_name || file.name;
      showPreview();
    } else {
      S.preview = null;
      S.name = file.name;
      showCannot(answerOf(res), "", false);
    }
  }

  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    fileInput.value = "";
    handleFile(f);
  });
  // A file dropped anywhere else must not make the browser navigate away
  ["dragover", "drop"].forEach(t => document.addEventListener(t, e => e.preventDefault()));
  ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); if (!S.busy) drop.classList.add("over"); }));
  drop.addEventListener("dragleave", e => { if (!drop.contains(e.relatedTarget)) drop.classList.remove("over"); });
  drop.addEventListener("drop", e => {
    e.preventDefault();
    drop.classList.remove("over");
    const f = e.dataTransfer && e.dataTransfer.files[0];
    handleFile(f);
  });

  // ---- Board pieces -----------------------------------------------------------------------------

  function mkButton(b) {
    const n = b.href ? el("a", `btn ${b.cls}`) : el("button", `btn ${b.cls}`);
    if (b.href) n.href = b.href; else n.type = "button";
    if (b.icon) n.insertAdjacentHTML("beforeend", b.icon);
    n.append(b.text);
    if (b.fn) n.addEventListener("click", b.fn);
    return n;
  }

  // The answer block: one headline, one sentence, at most one button. The count gets the highlighter band.
  function buildAnswer({ headline, sub, buttons = [], extra = null }) {
    const h1 = el("h1", "big num");
    h1.tabIndex = -1;
    const m = /^(\d+ de \d+ envíos?)([\s\S]*)$/.exec(headline);
    if (m) h1.append(el("span", "hl num", m[1]), m[2]); else h1.textContent = headline;
    const kids = [h1];
    if (sub) kids.push(el("p", "sub", sub));
    const actions = buttons.map(mkButton);
    if (extra) actions.push(extra);
    if (actions.length) {
      const a = el("div", "actions");
      a.append(...actions);
      kids.push(a);
    }
    return { h1, kids };
  }
  function renderFinal(opts) {
    const { h1, kids } = buildAnswer(opts);
    final.replaceChildren(...kids);
    return h1;
  }

  function techDetails(label, text, remito) {
    const d = el("details", "tech");
    const s = el("summary");
    s.insertAdjacentHTML("beforeend", CHEVRON);
    s.append(label);
    if (remito) s.append(el("span", "vh", ` de ${remito}`));
    d.append(s, el("div", "tech-body", text));
    return d;
  }

  const legendRows = new Map();
  LEGEND.forEach(([k, label]) => {
    const li = el("li");
    li.hidden = true;
    const sw = el("span", `sw ${k}`);
    sw.innerHTML = icon(k);
    const n = el("span", "n");
    li.append(sw, el("span", null, label), n);
    legend.append(li);
    legendRows.set(k, { li, n });
  });
  // Only states that have something in them are listed
  function renderLegend(c) {
    let any = false;
    STATES.forEach(k => {
      const r = legendRows.get(k);
      r.li.hidden = !(c[k] > 0);
      r.n.textContent = c[k] || 0;
      any = any || c[k] > 0;
    });
    legend.hidden = !any;
  }

  function buildMap(shipments, waiting) {
    S.tiles = new Map();
    const frag = document.createDocumentFragment();
    shipments.forEach(s => {
      const li = el("li");
      const b = el("button", "tile pend");
      b.type = "button";
      b.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-disabled", "true");
      b.tabIndex = -1;
      b.dataset.remito = s.remito;
      b.setAttribute("aria-label", `${s.recipient}, ${s.remito}: ${waiting}`);
      const row = el("span", "row num");
      row.append(el("span", null, s.remito.slice(-3)), el("span", "ic"));
      b.append(el("span", "name", s.recipient), row);
      li.append(b);
      frag.append(li);
      S.tiles.set(s.remito, b);
    });
    mapEl.replaceChildren(frag);
  }

  // The icon is placed while the tile still looks empty and the style is flushed before `pend` goes,
  // so the pop and the fill animate from the empty state.
  function fillTile(tile, r) {
    if (!PATHS[r.state]) return;
    tile.classList.remove(...STATES);
    tile.querySelector(".ic").innerHTML = icon(r.state);
    if (r.state === "prev" && !tile.querySelector(".hatch")) {
      const h = el("span", "hatch");
      h.setAttribute("aria-hidden", "true");
      tile.prepend(h);
    }
    tile.classList.add(r.state);
    void tile.offsetWidth;
    tile.classList.remove("pend");
    tile.removeAttribute("aria-disabled");
    tile.removeAttribute("tabindex");
    tile.setAttribute("aria-label", `${r.recipient}, ${r.remito}: ${r.label}`);
  }

  function setMap(titleText, subText) {
    $("map-title").textContent = titleText;
    const sub = $("map-sub");
    sub.hidden = !subText;
    sub.textContent = subText || "";
  }

  function resetBoard() {
    S.byRemito.clear(); S.seen.clear();
    S.counts = { ok: 0, prev: 0, fix: 0, none: 0 };
    S.filled = 0;
    renderLegend(S.counts);
    clearSelection();
    picked.hidden = true;
    fixesSection.hidden = true;
    sheet.replaceChildren();
    announce.textContent = "";
    overview.classList.remove("solo");
    $("map-section").hidden = false;
    body.classList.remove("running");
  }

  // ---- Step 1b: preview --------------------------------------------------------------------------

  function showPreview() {
    closeStream();
    const p = S.preview;
    const n = p.shipments.length;
    resetBoard();
    setMeta([p.export_name]);
    setTitle(n ? p.title : "");
    setView("preview");
    if (!n) {
      overview.classList.add("solo");
      $("map-section").hidden = true;
      renderFinal({
        headline: "No hay envíos para Expreso Andino en este archivo.",
        sub: p.sub,
        buttons: [{ text: "Elegir otro archivo", cls: "btn-primary", fn: () => showPick("", true) }],
      }).focus();
      return;
    }
    buildMap(p.shipments, "Sin cargar");
    setMap(`Los ${n} envíos de esta carga`);
    renderFinal({
      headline: p.title,
      sub: p.sub,
      buttons: [
        { text: p.button, cls: "btn-primary", fn: startRun },
        { text: "Elegir otro archivo", cls: "btn-quiet", fn: () => showPick("", true) },
      ],
    });
    final.querySelector(".btn-primary").focus();
  }

  // ---- Step 2: live load ------------------------------------------------------------------------

  async function startRun() {
    if (S.busy || !S.exportId) return showPick("", true);
    S.busy = true;
    S.at = new Date().toISOString();
    final.querySelectorAll("button").forEach(b => { b.disabled = true; });
    const res = await api("/api/runs", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ export_id: S.exportId }),
    });
    S.busy = false;
    if (res.status !== 202 || !res.data || !res.data.run_id) return showCannot(answerOf(res), "", !!S.preview);
    memory.write({ runId: res.data.run_id, exportId: S.exportId, name: S.name, at: S.at, preview: S.preview });
    beginLive(res.data.run_id);
  }
  const retryRun = () => (S.exportId ? startRun() : showPick("", true));

  function beginLive(runId) {
    const p = S.preview;
    const n = p.shipments.length;
    S.runId = runId;
    S.n = n;
    resetBoard();
    buildMap(p.shipments, "esperando");
    setMap(`Los ${n} envíos de esta carga`);
    $("live-k").textContent = "0";
    $("live-n").textContent = String(n);
    setMeta([timeLabel(S.at), p.export_name]);
    // The live block is shorter than the sentence it replaces; lift the legend by the difference
    legend.style.setProperty("--lift", `${Math.max(0, final.offsetHeight - liveBox.offsetHeight)}px`);
    body.classList.add("running");
    setView("running");
    announce.textContent = `Cargando ${envios(n)}.`;
    $("live-text").focus();

    openStream(runId);
  }

  function openStream(runId) {
    closeStream();
    const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
    S.es = es;
    const on = (name, fn) => es.addEventListener(name, e => {
      let data;
      try { data = JSON.parse(e.data); } catch (_) { return; }
      fn(data);
    });
    on("result", onResult);
    on("done", onDone);
    on("failed", onFailed);
    es.onerror = async () => {
      if (es.readyState !== EventSource.CLOSED) return; // the browser is reconnecting; repeated events are ignored by index
      closeStream();
      // The stream is gone for good: ask for the run as it stands
      const res = await api(`/api/runs/${encodeURIComponent(runId)}`);
      const d = res.data;
      if (res.status === 202 && d && d.running) setTimeout(() => openStream(runId), 500);
      else if (res.ok && d && d.results) onDone(d);
      else if (res.ok && d && d.answer) onFailed(d);
      else onFailed({ answer: FALLBACK, technical: "" });
    };
  }

  function onResult(rv) {
    if (S.seen.has(rv.index)) return;
    S.seen.add(rv.index);
    if (rv.duplicate || !rv.state) return;
    const tile = S.tiles.get(rv.remito);
    if (!tile || !PATHS[rv.state]) return;
    S.byRemito.set(rv.remito, rv);
    fillTile(tile, rv);
    S.counts[rv.state]++;
    S.filled++;
    $("live-k").textContent = String(S.filled);
    renderLegend(S.counts);
    const half = Math.floor(S.n / 2);
    if (half >= 2 && S.filled === half) announce.textContent = `Van ${half} de ${S.n}.`;
  }

  // ---- Step 3: result ---------------------------------------------------------------------------

  // What a button does comes from the server's `action`, never from its text. `retry` is the caller's.
  function buttonsFor(a, retry = retryRun) {
    const t = a.button;
    const act = {
      show_fixes: { href: "#para-corregir", fn: toFixes },
      reload: { fn: () => showPick(S.name, true) },
      retry: { fn: retry },
      pick_other: { fn: () => showPick("", true) },
    }[a.action];
    return t && act ? [{ text: t, cls: "btn-primary", ...act }] : [];
  }

  function problemsOf(r) {
    return r.problems && r.problems.length ? r.problems : [{ title: r.picked || r.label, hint: "" }];
  }

  function sheetRow(r, kind, hold) {
    const tr = el("tr");
    tr.dataset.remito = r.remito;
    if (hold) { tr.classList.add("hold"); tr.inert = true; }
    const what = el("td");
    problemsOf(r).forEach(p => {
      const prob = el("div", "prob");
      const w = el("div", kind === "none" ? "what none" : "what");
      w.insertAdjacentHTML("beforeend", icon(kind, 18));
      w.append(p.title);
      prob.append(w);
      if (p.hint) prob.append(el("p", "why", p.hint));
      what.append(prob);
    });
    const who = el("td");
    who.append(el("div", "who", r.recipient), el("div", "who-sub", r.address));
    const tech = el("td");
    if (r.technical) tech.append(techDetails("Ver detalle técnico", r.technical, r.remito));
    tr.append(what, who, el("td", null, r.client), el("td", "num", r.remito), tech);
    return tr;
  }

  function sheetGroup({ id, title, note, rows, kind, firstGroup, hold }) {
    const g = el("div", "group");
    const head = el("div", "fixes-head");
    const h = el("h2", null, title);
    h.id = id;
    head.append(h);
    if (note) head.append(el("p", null, note));
    const table = el("table", "fix-table");
    table.setAttribute("aria-labelledby", id);
    const cols = el("colgroup");
    [28, 20, 18, 11, 23].forEach(w => { const c = el("col"); c.style.width = `${w}%`; cols.append(c); });
    const thead = el("thead", firstGroup ? null : "vh");
    const tr = el("tr");
    ["Qué pasa", "Envío para", "Cliente", "Remito"].forEach(t => { const th = el("th", null, t); th.scope = "col"; tr.append(th); });
    const last = el("th");
    last.scope = "col";
    last.append(el("span", "vh", "Detalle técnico"));
    tr.append(last);
    thead.append(tr);
    const tbody = el("tbody");
    tbody.append(...rows.map(r => sheetRow(r, kind, hold)));
    table.append(cols, thead, tbody);
    g.append(head, table);
    return g;
  }

  function renderSheet(rv, hold) {
    const fix = rv.results.filter(r => r.state === "fix");
    const none = rv.results.filter(r => r.state === "none");
    fixesSection.hidden = !(fix.length || none.length);
    if (fixesSection.hidden) { sheet.replaceChildren(); return; }
    const groups = [];
    if (fix.length) {
      groups.push(sheetGroup({
        id: "fixes-title", title: "Para corregir en LogiSur", rows: fix, kind: "fix", firstGroup: true, hold,
        note: "Cuando los corrijas, volvé a cargar el export. No se duplica nada.",
      }));
    }
    if (none.length) {
      groups.push(sheetGroup({
        id: fix.length ? "none-title" : "fixes-title", title: "Sin respuesta de Expreso Andino",
        rows: none, kind: "none", firstGroup: !fix.length, hold,
      }));
    }
    fixesSection.setAttribute("aria-labelledby", "fixes-title");
    const actions = el("div", "sheet-actions");
    // The answer already carries this button when only "Sin respuesta" is left
    if (rv.answer.action !== "reload") {
      actions.append(mkButton({ text: "Volver a cargar el export", cls: "btn-quiet", icon: UPLOAD, fn: () => showPick(S.name, true) }));
    }
    const dups = rv.results.filter(r => r.duplicate).length;
    const c = rv.counts;
    const t = el("div", "tech-body");
    t.append(rv.report_file || "", document.createElement("br"),
      `Cargado ${c.ok} · Ya estaba ${c.prev} · Duplicado en el export ${dups} · Para corregir ${c.fix} · Sin respuesta ${c.none}`);
    const d = el("details", "tech");
    const s = el("summary");
    s.insertAdjacentHTML("beforeend", CHEVRON);
    s.append("Ver detalle técnico de la carga");
    d.append(s, t);
    actions.append(d);
    sheet.replaceChildren(...groups, actions);
  }

  // One ring leaves each tile that needs a person, only when a load ends by itself
  function settlePing() {
    if (reduceMotion.matches) return;
    [...mapEl.querySelectorAll(".tile.fix, .tile.none")].forEach((t, p) => {
      t.style.setProperty("--p", p);
      t.classList.add("ping");
      t.addEventListener("animationend", () => t.classList.remove("ping"), { once: true });
    });
  }

  function onDone(rv) {
    closeStream();
    announce.textContent = ""; // the "Cargando…" progress status is over
    const natural = body.classList.contains("running");
    S.name = rv.export_name || S.name;
    S.byRemito.clear();
    rv.results.forEach(r => {
      if (!r.duplicate && r.state) S.byRemito.set(r.remito, r);
    });
    // The RunView is the source of truth: tiles that missed their event are filled now, wrong ones corrected
    S.byRemito.forEach((r, remito) => {
      const t = S.tiles.get(remito);
      if (t && (t.classList.contains("pend") || !t.classList.contains(r.state))) fillTile(t, r);
    });

    renderFinal({ headline: rv.answer.headline, sub: rv.answer.sub, buttons: buttonsFor(rv.answer) });
    renderLegend(rv.counts);
    renderSheet(rv, natural);
    setMap(`Los ${rv.shipments_total} envíos de esta carga`);
    setMeta([timeLabel(rv.generated_at), rv.export_name]);
    setTitle(rv.answer.headline);
    clearSelection();
    picked.hidden = false;
    // Same lift trick as the start: the legend keeps its place under the counter and glides back down
    legend.style.setProperty("--lift", `${Math.max(0, final.offsetHeight - liveBox.offsetHeight)}px`);
    const active = document.activeElement;
    const lost = active === document.body || liveBox.contains(active) || final.contains(active);
    body.classList.remove("running");
    setView("result");
    void final.offsetWidth;
    if (lost) final.querySelector("h1").focus();
    else announce.textContent = rv.answer.headline;
    if (natural) {
      void sheet.offsetWidth;
      sheet.querySelectorAll("tr.hold").forEach(tr => { tr.classList.remove("hold"); tr.inert = false; });
      settlePing();
    }
  }

  // ---- Cannot-run screens -----------------------------------------------------------------------

  function onFailed(f) {
    closeStream();
    announce.textContent = "";
    showCannot(f.answer || FALLBACK, f.technical || "", true);
  }

  // withMap: the preview is known, so its slots stay on screen (empty, or filled with what did get through)
  function showCannot(answer, technical, withMap) {
    body.classList.remove("running");
    const p = withMap ? S.preview : null;
    if (p) {
      S.tiles.forEach((t, remito) => {
        if (!t.classList.contains("pend")) return;
        const s = p.shipments.find(x => x.remito === remito);
        t.setAttribute("aria-label", `${s.recipient}, ${remito}: Sin cargar`);
      });
      const n = p.shipments.length;
      overview.classList.remove("solo");
      $("map-section").hidden = false;
      setMap(p.title, `${p.export_name} · ${p.sub}`);
      picked.hidden = S.filled === 0;
      if (S.filled) setPicked("", [el("span", "k", IDLE)]);
    } else {
      overview.classList.add("solo");
      $("map-section").hidden = true;
      picked.hidden = true;
    }
    fixesSection.hidden = true;
    sheet.replaceChildren();
    renderLegend(S.counts);
    setMeta([timeLabel(S.at), p ? p.export_name : S.name]);
    setTitle(answer.headline);
    setView("cannot");
    const extra = technical ? techDetails("Ver detalle técnico", technical) : null;
    renderFinal({ headline: answer.headline, sub: answer.sub, buttons: buttonsFor(answer), extra }).focus();
  }

  // ---- Selection and the picked line ------------------------------------------------------------

  let swapTimer = 0;
  const setPicked = (key, nodes) => {
    clearTimeout(swapTimer);
    if (picked.dataset.key === key && picked.childNodes.length) return;
    picked.dataset.key = key;
    picked.classList.add("swap");
    swapTimer = setTimeout(() => { picked.replaceChildren(...nodes); picked.classList.remove("swap"); }, 60);
  };
  function clearSelection() {
    S.selected = null;
    mapEl.querySelectorAll(".tile").forEach(t => t.setAttribute("aria-pressed", "false"));
    sheet.querySelectorAll("tr.lit").forEach(tr => tr.classList.remove("lit"));
    clearTimeout(swapTimer);
    picked.classList.remove("swap");
    picked.dataset.key = "";
    picked.replaceChildren(el("span", "k", IDLE));
  }

  function pickedNodes(r) {
    const nodes = [el("strong", null, r.recipient)];
    if (r.state === "fix" || r.state === "none") {
      nodes.push(el("span", null, r.picked || problemsOf(r).map(p => p.title).join(". ")));
      const a = el("a", "link", r.state === "fix" ? "Ver cómo corregirlo" : "Ver qué pasó");
      a.href = "#para-corregir";
      a.dataset.remito = r.remito;
      nodes.push(a);
      return nodes;
    }
    nodes.push(el("span", null, r.picked), el("span", "k", r.remito));
    // A shipment confirmed after a retry keeps the bridge's own words one click away
    if (r.technical) nodes.push(techDetails(`Ver detalle técnico de ${r.remito}`, r.technical));
    return nodes;
  }

  mapEl.addEventListener("click", e => {
    const b = e.target.closest(".tile");
    if (!b || b.classList.contains("pend")) return;
    const r = S.byRemito.get(b.dataset.remito);
    if (!r) return;
    S.selected = r.remito;
    mapEl.querySelectorAll(".tile").forEach(t => t.setAttribute("aria-pressed", String(t === b)));
    sheet.querySelectorAll("tr").forEach(tr => tr.classList.toggle("lit", tr.dataset.remito === r.remito));
    setPicked(r.remito, pickedNodes(r));
  });

  // "Ver cómo corregirlo": smooth scroll (only if motion is welcome and the click is not from the keyboard),
  // then one attention highlight that holds, then fades out.
  const flash = row => {
    row.classList.remove("flash");
    void row.offsetWidth;
    row.classList.add("flash");
    row.addEventListener("animationend", () => row.classList.remove("flash"), { once: true });
  };
  const inView = n => { const r = n.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; };
  const smoothOk = e => !reduceMotion.matches && e.detail !== 0;
  picked.addEventListener("click", e => {
    const a = e.target.closest("a[data-remito]");
    const row = a && [...sheet.querySelectorAll("tr")].find(tr => tr.dataset.remito === a.dataset.remito);
    if (!row) return;
    e.preventDefault();
    const smooth = smoothOk(e) && !inView(row);
    row.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "center" });
    row.tabIndex = -1;
    row.focus({ preventScroll: true });
    if (!smooth) return flash(row);
    let done = false;
    const go = () => { if (!done) { done = true; flash(row); } };
    addEventListener("scrollend", go, { once: true });
    setTimeout(go, 700);
  });
  function toFixes(e) {
    if (!smoothOk(e)) return;
    e.preventDefault();
    fixesSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---- Overdue shipments ------------------------------------------------------------------------

  const odTitle = $("od-title");
  const odBody = $("od-body");
  const odDate = $("od-date");
  const odBack = $("od-back");
  const openOverdue = $("open-overdue");
  let odFrom = "result";
  let odToken = 0;

  const todayISO = () => {
    const d = new Date();
    const p = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  };

  function overdueRow(item) {
    const li = el("li", "od-row");
    const who = el("div");
    who.append(el("div", "od-who", item.recipient));
    const sub = el("div", "sub-line");
    sub.append(el("span", "vh", "Cliente: "), item.client, " · ", el("span", "vh", "Ciudad: "), item.city);
    who.append(sub);
    const remito = el("div", "num");
    remito.append(el("span", "vh", "Remito: "), item.remito);
    const status = el("div");
    status.append(el("div", "od-status", item.status_text), el("div", "sub-line", item.late_line));
    li.append(who, remito, status);
    return li;
  }

  function renderOverdue(data) {
    odTitle.textContent = data.title;
    setTitle(data.title);
    $("od-announce").textContent = data.title;
    if (!data.items.length) {
      odBody.replaceChildren(el("p", "od-empty", data.empty));
      return;
    }
    const ul = el("ul", "od-list");
    ul.setAttribute("aria-label", data.title);
    ul.append(...data.items.map(overdueRow));
    odBody.replaceChildren(ul);
  }

  function renderOverdueCannot(res) {
    const d = res.data;
    const answer = d && d.answer ? d.answer : OVERDUE_FALLBACK;
    const technical = d && d.answer ? d.technical || "" : "";
    const extra = technical ? techDetails("Ver detalle técnico", technical) : null;
    const { h1, kids } = buildAnswer({ headline: answer.headline, sub: answer.sub, buttons: buttonsFor(answer, loadOverdue), extra });
    // The heading is the page's h1 for this view; the answer's own headline is only text here
    odTitle.textContent = answer.headline;
    setTitle(answer.headline);
    $("od-announce").textContent = answer.headline;
    const box = el("div", "answer");
    box.append(...kids.slice(1));
    odBody.replaceChildren(box);
  }

  async function loadOverdue() {
    const iso = odDate.value;
    if (!iso || !S.exportId) return;
    const token = ++odToken;
    odBody.setAttribute("aria-busy", "true");
    const res = await api(`/api/exports/${encodeURIComponent(S.exportId)}/overdue?today=${encodeURIComponent(iso)}`);
    if (token !== odToken) return; // a newer date was asked for
    odBody.removeAttribute("aria-busy");
    if (res.ok && res.data && Array.isArray(res.data.items)) renderOverdue(res.data);
    else renderOverdueCannot(res);
  }

  const inOverdueEntry = () => !!(history.state && history.state.panel === "overdue");

  function showOverdue(fromHistory) {
    if (!S.exportId) return;
    if (fromHistory !== true) history.pushState({ panel: "overdue" }, "");
    odFrom = body.dataset.view === "preview" ? "preview" : "result";
    odBack.textContent = odFrom === "preview" ? "Volver a los envíos" : "Volver al resultado";
    odDate.value = todayISO();
    odTitle.textContent = "Buscando envíos atrasados…";
    odBody.replaceChildren();
    setView("overdue");
    setTitle("Envíos atrasados");
    odTitle.focus();
    loadOverdue();
  }

  function hideOverdue() {
    odToken++;
    odBody.removeAttribute("aria-busy");
    setView(odFrom);
    setTitle(odFrom === "preview" ? (S.preview && S.preview.title) || "" : (final.querySelector("h1") || {}).textContent || "");
    openOverdue.focus();
  }

  openOverdue.addEventListener("click", () => showOverdue());
  // Going back is the browser's Back: the pushed entry is popped and popstate does the rest
  odBack.addEventListener("click", () => (inOverdueEntry() ? history.back() : hideOverdue()));
  odDate.addEventListener("change", loadOverdue);
  addEventListener("popstate", () => {
    const view = body.dataset.view;
    if (view === "overdue") hideOverdue();
    else if (inOverdueEntry() && (view === "preview" || view === "result")) showOverdue(true);
  });

  // ---- Reload: bring back the run this tab was showing ------------------------------------------

  const shipmentsOf = rv => rv.results.filter(r => r.state && !r.duplicate).map(r => ({ remito: r.remito, recipient: r.recipient }));

  async function restoreRun(mem) {
    const res = await api(`/api/runs/${encodeURIComponent(mem.runId)}`);
    const d = res.data;
    S.exportId = mem.exportId || null;
    S.preview = mem.preview || null;
    S.name = mem.name || "";
    S.at = mem.at || "";
    body.classList.remove("booting"); // what follows is one synchronous render: the pick screen never shows
    if (res.status === 202 && d && d.running && S.preview) {
      beginLive(mem.runId);
    } else if (res.status === 200 && d && d.results) {
      resetBoard();
      buildMap(shipmentsOf(d), "Sin cargar");
      onDone(d);
    } else if (res.status === 200 && d && d.answer) {
      showCannot(d.answer, d.technical || "", false);
    } else {
      showPick(mem.name || "", false); // the server forgot the run (or is gone): back to the start, without a word
    }
    requestAnimationFrame(() => requestAnimationFrame(() => body.classList.remove("restoring")));
  }

  // Opened by the launcher without expreso.ini: loads go to the kit's mock API, and the header says so
  api("/api/config").then(res => { $("mode").hidden = !(res.ok && res.data && res.data.testMode === true); });

  // An overdue entry that survived a reload has no view behind it any more
  if (inOverdueEntry()) history.replaceState(null, "");
  const remembered = memory.read();
  if (remembered && remembered.runId) {
    body.classList.add("booting", "restoring");
    restoreRun(remembered);
  } else {
    showPick((remembered && remembered.name) || "", false);
  }
})();
