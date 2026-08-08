/* Aegis front end.
 *
 * Two jobs: stream the trace onto the tape as it happens, and render the
 * finished briefing. Trace events arrive twice, once when a span opens
 * ("running") and once when it closes, so lines are keyed by event id and
 * updated in place rather than appended twice.
 */

const $ = (id) => document.getElementById(id);

const tape = $("tape");
const briefing = $("briefing");
const traceMeta = $("trace-meta");
const briefingMeta = $("briefing-meta");
const runButton = $("run");

let source = null;
let startedAt = 0;
let depths = {};

const EXAMPLES = [
  ["4521", "Prep me for tomorrow's meeting. The client is asking about the Solaris AI fund"],
  ["4526", "Client wants to put £150k into Bramble private credit. Can we do it?"],
  ["4522", "Review the portfolio and flag anything I should raise on concentration"],
  ["4527", "The client has read about the Lyra leveraged note and wants in"],
  ["4523", "Would the Zephyr precious metals fund work as a diversifier here?"],
  ["4524", "Routine annual review. Anything blocking?"],
  ["4525", "Can we add Bramble private credit for this client?"],
  ["4528", "What's the market context I should bring to the meeting?"]
];

/* ------------------------------------------------------------------ boot */
async function boot() {
  try {
    const [health, clients] = await Promise.all([
      fetch("/api/health").then((r) => {
        if (!r.ok) throw new Error("no backend");
        return r.json();
      }),
      fetch("/api/clients").then((r) => r.json())
    ]);

    $("st-llm").textContent = `llm ${health.llm_provider}/${health.llm_model}` +
      (health.using_mock_llm ? " (no api key, deterministic mode)" : "");
    $("st-embed").textContent = `embedding ${health.embedding_model}`;
    $("st-index").textContent = `index ${health.chunks_indexed} chunks`;
    $("st-agents").textContent = `${health.agents} agents · ${health.tools} tools`;

    const select = $("client");
    clients.clients.forEach((c) => {
      const option = document.createElement("option");
      option.value = c.client_id;
      option.textContent = `${c.client_id} · ${c.name.replace(" (SYNTHETIC)", "")} · ${c.risk_profile}`;
      select.appendChild(option);
    });
  } catch (err) {
    await enableReplay();
  }

  const box = $("examples");
  const examples = replay ? replay.map((r) => [r.client_id, r.query]) : EXAMPLES;
  examples.forEach(([clientId, text]) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = `${clientId} · ${text}`;
    chip.addEventListener("click", () => {
      $("client").value = clientId;
      $("query").value = text;
      $("briefing-form").requestSubmit();
    });
    box.appendChild(chip);
  });
}

/* --------------------------------------------------------------- replay */
/* When there is no backend, as on a GitHub Pages deploy, the page replays
 * runs that were recorded from a real local execution by demo/build_demo.py.
 * The trace and briefing are genuine output, not mocked fixtures; only the
 * timing is synthesised, because a deterministic run finishes in ~10ms and
 * would otherwise appear instantly. The status line says so plainly. */

let replay = null;

async function enableReplay() {
  try {
    replay = await fetch("./runs/manifest.json").then((r) => r.json());
  } catch (err) {
    $("st-llm").textContent = "backend unreachable. Start it with: uvicorn main:app --reload";
    return;
  }

  const meta = replay.meta || {};
  $("st-llm").textContent = `llm ${meta.llm || "·"}`;
  $("st-embed").textContent = `embedding ${meta.embedding || "·"}`;
  $("st-index").textContent = `index ${meta.chunks ?? "·"} chunks`;
  $("st-agents").textContent = `${meta.agents ?? "·"} agents · ${meta.tools ?? "·"} tools`;
  document.querySelector(".statusline__item--notice").textContent =
    "recorded run · static replay · synthetic data";

  replay = replay.runs || [];

  const select = $("client");
  const seen = new Set();
  replay.forEach((r) => {
    if (seen.has(r.client_id)) return;
    seen.add(r.client_id);
    const option = document.createElement("option");
    option.value = r.client_id;
    option.textContent = r.client_label;
    select.appendChild(option);
  });

  const note = document.createElement("p");
  note.className = "notice";
  note.style.marginTop = "10px";
  note.textContent =
    "This is a static replay of runs recorded from a real local execution. " +
    "there is no backend on this page. Pick a scenario below to play one back. " +
    "Clone the repo and run uvicorn to make live requests.";
  $("examples").parentElement.appendChild(note);
}

function findRecordedRun(clientId, query) {
  const exact = replay.find((r) => r.query === query);
  if (exact) return exact;
  const byClient = replay.find((r) => r.client_id === clientId);
  return byClient || replay[0];
}

async function playRecorded(clientId, query) {
  const record = findRecordedRun(clientId, query);
  if (!record) return;

  $("query").value = record.query;
  $("client").value = record.client_id;
  traceMeta.textContent = `run ${record.run_id} (recorded)`;

  const data = await fetch(`./runs/${record.file}`).then((r) => r.json());
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  for (const ev of data.trace) {
    if (ev.kind !== "note") {
      printEvent({ ...ev, status: "running", ended_at: null, duration_ms: null, output: null });
      await pause(reduceMotion ? 0 : cadence(ev));
    }
    printEvent(ev);
    await pause(reduceMotion ? 0 : 26);
  }

  renderBriefing(data.briefing, data.plan);
  finishLine(data.trace_summary);
  traceMeta.textContent =
    `run ${data.trace_summary.run_id} · ${data.trace_summary.events} events · recorded`;
  stop();
}

/* Real durations here are single-digit milliseconds, so replaying them
 * faithfully would look like nothing happened. These are readable stand-ins,
 * weighted by the kind of work each step represents. */
function cadence(ev) {
  return { llm: 240, retrieval: 130, tool: 90, agent: 70 }[ev.kind] ?? 60;
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/* ------------------------------------------------------------------- run */
$("briefing-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run($("client").value, $("query").value.trim());
});

function run(clientId, query) {
  if (!query) return;
  if (source) source.close();

  tape.innerHTML = "";
  briefing.innerHTML = `<p class="empty">Working. The briefing appears once every agent has reported back.</p>`;
  briefingMeta.textContent = "running";
  runButton.disabled = true;
  runButton.querySelector(".run__label").textContent = "Working…";
  startedAt = performance.now();
  depths = {};

  if (replay) {
    playRecorded(clientId, query);
    return;
  }

  const url = `/api/briefing/stream?client_id=${encodeURIComponent(clientId)}&query=${encodeURIComponent(query)}`;
  source = new EventSource(url);

  source.addEventListener("start", (e) => {
    const data = JSON.parse(e.data);
    traceMeta.textContent = `run ${data.run_id}`;
  });

  source.addEventListener("trace", (e) => printEvent(JSON.parse(e.data)));

  source.addEventListener("result", (e) => {
    const data = JSON.parse(e.data);
    renderBriefing(data.briefing, data.plan);
    const s = data.trace_summary;
    traceMeta.textContent = `run ${s.run_id} · ${s.events} events · ${Math.round(s.elapsed_ms)} ms`;
    finishLine(s);
    stop();
  });

  source.addEventListener("error", (e) => {
    let message = "The connection dropped before the briefing finished.";
    try { message = JSON.parse(e.data).error; } catch (_) { /* transport-level */ }
    briefing.innerHTML = `<p class="empty">${escapeHtml(message)}</p>`;
    briefingMeta.textContent = "failed";
    stop();
  });
}

function stop() {
  if (source) source.close();
  source = null;
  runButton.disabled = false;
  runButton.querySelector(".run__label").textContent = "Generate briefing";
}

/* ------------------------------------------------------------ the tape */
function printEvent(ev) {
  let row = document.getElementById(`ev-${ev.id}`);
  if (!row) {
    row = document.createElement("div");
    row.id = `ev-${ev.id}`;
    row.className = "ev";
    depths[ev.id] = ev.parent_id && depths[ev.parent_id] !== undefined
      ? Math.min(depths[ev.parent_id] + 1, 3)
      : 0;
    row.innerHTML = rowMarkup(ev, depths[ev.id]);
    tape.appendChild(row);
    wireToggle(row);
    tape.scrollTop = tape.scrollHeight;
  } else {
    const wasOpen = !row.querySelector(".ev__detail")?.hidden;
    row.innerHTML = rowMarkup(ev, depths[ev.id] ?? 0);
    wireToggle(row, wasOpen);
  }
  row.className = `ev ev--${ev.status} ev--${ev.kind} ev--depth${depths[ev.id] ?? 0}`;
}

function rowMarkup(ev, depth) {
  const time = (ev.started_at || "").slice(11, 23);
  const dur = ev.duration_ms === null || ev.duration_ms === undefined
    ? "···"
    : ev.duration_ms >= 1000
      ? `${(ev.duration_ms / 1000).toFixed(2)}s`
      : `${Math.round(ev.duration_ms)}ms`;

  const hasDetail = ev.input !== null || ev.output !== null || ev.error;
  const detail = hasDetail ? `
    <div class="ev__detail" hidden>
      ${ev.error ? `<h4>error</h4><pre>${escapeHtml(ev.error)}</pre>` : ""}
      ${ev.input !== null && ev.input !== undefined ? `<h4>input</h4><pre>${escapeHtml(pretty(ev.input))}</pre>` : ""}
      ${ev.output !== null && ev.output !== undefined ? `<h4>output</h4><pre>${escapeHtml(pretty(ev.output))}</pre>` : ""}
    </div>` : "";

  return `
    <span class="ev__time">${time}</span>
    <span class="ev__dur">${dur}</span>
    <div class="ev__body">
      <button class="ev__line" type="button" ${hasDetail ? "" : 'aria-disabled="true"'}>
        <span class="ev__kind">${ev.kind}</span>
        <span class="ev__label" title="${escapeHtml(ev.label)}">${escapeHtml(ev.label)}</span>
        ${hasDetail ? '<span class="ev__caret">+</span>' : ""}
      </button>
      ${detail}
    </div>`;
}

function wireToggle(row, openIt = false) {
  const line = row.querySelector(".ev__line");
  const detail = row.querySelector(".ev__detail");
  if (!line || !detail) return;
  if (openIt) {
    detail.hidden = false;
    const caret = row.querySelector(".ev__caret");
    if (caret) caret.textContent = "−";
  }
  line.addEventListener("click", () => {
    detail.hidden = !detail.hidden;
    const caret = row.querySelector(".ev__caret");
    if (caret) caret.textContent = detail.hidden ? "+" : "−";
  });
}

function finishLine(summary) {
  const end = document.createElement("p");
  end.className = "tape__end";
  const kinds = Object.entries(summary.by_kind)
    .map(([k, n]) => `${n} ${k}`)
    .join(" · ");
  end.textContent = `end of trace · ${kinds} · ${summary.errors} error(s) · ${Math.round(summary.elapsed_ms)} ms total`;
  tape.appendChild(end);
  tape.scrollTop = tape.scrollHeight;
}

/* --------------------------------------------------------- the briefing */
function renderBriefing(b, plan) {
  const c = b.client;
  const comp = b.compliance;
  const snap = b.portfolio_snapshot;
  const market = b.market_context;
  const markers = new Set((b.citations || []).map((s) => s.marker));

  const holdings = (snap.holdings || []).map((h) => `
    <tr>
      <td class="tick">${escapeHtml(h.instrument_id)}</td>
      <td>${escapeHtml(h.name)}<span class="bar" style="width:${Math.min(h.weight_pct * 2.6, 100)}%"></span></td>
      <td class="num">${h.risk_rating}/7</td>
      <td class="num">${h.weight_pct.toFixed(1)}%</td>
      <td class="num">£${Math.round(h.value_gbp).toLocaleString("en-GB")}</td>
      <td class="num">${h.ytd_return_pct > 0 ? "+" : ""}${h.ytd_return_pct.toFixed(1)}%</td>
    </tr>`).join("");

  const flags = (comp.flags || []).map((f) => `
    <div class="flag flag--${escapeHtml(f.severity)}">
      <div class="flag__head">
        <span class="flag__rule">${escapeHtml(f.rule_id)}</span>
        <span class="flag__name">${escapeHtml(f.rule_name)}</span>
        <span class="flag__sev">${escapeHtml(f.severity)}${f.instrument_id ? " · " + escapeHtml(f.instrument_id) : ""}</span>
      </div>
      <p class="flag__detail">${escapeHtml(f.detail)}</p>
      <p class="flag__fix">${escapeHtml(f.remediation)}</p>
    </div>`).join("");

  const points = (b.talking_points || []).map((p) => `
    <li>
      <p class="point__what">${cite(p.point, markers)}</p>
      ${p.why ? `<p class="point__why">${cite(p.why, markers)}</p>` : ""}
    </li>`).join("");

  const keyPoints = (market.key_points || []).map(
    (p) => `<li>${cite(p.point || "", markers)}</li>`).join("");

  const sources = (b.citations || []).map((s) => `
    <div class="source" id="src-${escapeHtml(s.marker)}">
      <div class="source__head">
        <span class="source__marker">[${escapeHtml(s.marker)}]</span>
        <span>${escapeHtml(s.title)} · ${escapeHtml(s.section)}</span>
        <span class="source__score">${escapeHtml(s.doc_type)} · sim ${s.score}</span>
      </div>
      <p class="source__doc">${escapeHtml(s.doc_id)} · ${escapeHtml(s.source_file)}</p>
      <p class="source__snippet">${escapeHtml(s.snippet)}</p>
    </div>`).join("");

  briefing.innerHTML = `
    <div class="bsection">
      <p class="who">${escapeHtml(c.name || "")} · ${escapeHtml(c.client_id || "")} ·
        ${escapeHtml(c.risk_profile || "")} · ${escapeHtml(c.investor_classification || "")} ·
        ${c.horizon_years}y horizon · ${escapeHtml(c.liquidity_needs || "")} liquidity ·
        meeting ${escapeHtml(c.next_meeting || "·")}</p>
      <h3 class="headline">${cite(b.headline || "", markers)}</h3>
      <p class="lede">${cite(b.summary || "", markers)}</p>
    </div>

    <div class="bsection">
      <h3 class="bsection__title">Compliance</h3>
      <div class="verdict verdict--${escapeHtml(comp.status)}">
        <span class="verdict__tag">${escapeHtml(comp.status)}</span>
        <span class="verdict__count">${comp.flag_count} flag(s) ·
          ${(comp.rules_evaluated || []).length} rule evaluations ·
          checked ${(comp.proposals_checked || []).join(", ") || "existing holdings only"}</span>
      </div>
      ${comp.adviser_note ? `<p class="lede">${escapeHtml(comp.adviser_note)}</p>` : ""}
      ${flags}
      ${(comp.actions_before_meeting || []).length ? `
        <h3 class="bsection__title" style="margin-top:14px">Before the meeting</h3>
        <ul class="plain">${comp.actions_before_meeting.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>` : ""}
      <p class="notice">${escapeHtml(comp.disclaimer || "")}</p>
    </div>

    <div class="bsection">
      <h3 class="bsection__title">Portfolio snapshot</h3>
      <div class="stats">
        <div class="stat"><span class="stat__k">Value</span><span class="stat__v">£${Math.round(snap.total_value_gbp || 0).toLocaleString("en-GB")}</span></div>
        <div class="stat"><span class="stat__k">YTD</span><span class="stat__v">${(snap.performance?.ytd_return_pct ?? 0).toFixed(1)}%</span></div>
        <div class="stat"><span class="stat__k">vs bench</span><span class="stat__v">${(snap.performance?.vs_benchmark_ytd_pct ?? 0).toFixed(1)}%</span></div>
        <div class="stat"><span class="stat__k">Growth assets</span><span class="stat__v">${snap.growth_asset_pct}%</span></div>
        <div class="stat"><span class="stat__k">Cash</span><span class="stat__v">${snap.cash_pct}%</span></div>
        <div class="stat"><span class="stat__k">Wtd risk</span><span class="stat__v">${snap.weighted_risk_rating}/7</span></div>
      </div>
      <table class="holdings">
        <thead><tr><th>Id</th><th>Holding</th><th class="num">Risk</th><th class="num">Weight</th><th class="num">Value</th><th class="num">YTD</th></tr></thead>
        <tbody>${holdings}</tbody>
      </table>
      <p class="notice">As at ${escapeHtml(snap.as_of || "")} · synthetic data</p>
    </div>

    <div class="bsection">
      <h3 class="bsection__title">Market context</h3>
      <p class="lede">${cite(market.summary || "", markers)}</p>
      ${keyPoints ? `<ul class="plain" style="margin-top:10px">${keyPoints}</ul>` : ""}
      ${market.relevance_to_client ? `<p class="point__why" style="margin-top:10px">${cite(market.relevance_to_client, markers)}</p>` : ""}
      ${(market.queries_run || []).length ? `<p class="notice">Retrieval queries: ${market.queries_run.map(escapeHtml).join(" · ")}</p>` : ""}
    </div>

    <div class="bsection">
      <h3 class="bsection__title">Talking points</h3>
      <ul class="points">${points || "<li>None generated.</li>"}</ul>
    </div>

    ${(b.questions_to_ask || []).length ? `
    <div class="bsection">
      <h3 class="bsection__title">Questions to ask</h3>
      <ul class="plain">${b.questions_to_ask.map((q) => `<li>${escapeHtml(q)}</li>`).join("")}</ul>
    </div>` : ""}

    ${(b.watch_items || []).length ? `
    <div class="bsection">
      <h3 class="bsection__title">Watch items</h3>
      <ul class="plain">${b.watch_items.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>
    </div>` : ""}

    <div class="bsection">
      <h3 class="bsection__title">Sources</h3>
      ${sources || '<p class="notice">No sources retrieved for this request.</p>'}
    </div>

    <div class="bsection">
      <h3 class="bsection__title">Orchestrator plan</h3>
      <p class="point__why">${escapeHtml(plan?.reasoning || "")}</p>
      <p class="notice">intent ${escapeHtml(plan?.intent || "·")} ·
        research ${plan?.run_research ? "yes" : "skipped"} ·
        instruments ${(plan?.candidate_instruments || []).join(", ") || "none"} ·
        forced ${(plan?.forced_steps || []).join(" → ")} ·
        planned by ${escapeHtml(plan?._generated_by || "·")}</p>
      <p class="notice">${escapeHtml(b.data_notice || "")}</p>
    </div>`;

  briefingMeta.textContent = `${comp.status} · ${(b.citations || []).length} sources`;
  wireCitations();
}

/* Turn [S1] / [S1, S3] markers into buttons that jump to the source. */
function cite(text, markers) {
  return escapeHtml(String(text || "")).replace(/\[(S\d+(?:,\s*S\d+)*)\]/g, (match, group) => {
    const parts = group.split(/,\s*/).filter((m) => markers.has(m));
    if (!parts.length) return "";
    return parts.map((m) => `<button class="cite" data-marker="${m}">${m}</button>`).join("");
  });
}

function wireCitations() {
  briefing.querySelectorAll(".cite").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(`src-${button.dataset.marker}`);
      if (!target) return;
      briefing.querySelectorAll(".source--lit").forEach((el) => el.classList.remove("source--lit"));
      target.classList.add("source--lit");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

/* ---------------------------------------------------------------- utils */
function pretty(value) {
  if (typeof value === "string") return value;
  try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[ch]);
}

boot();
