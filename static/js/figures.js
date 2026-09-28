// Interactive figures and tables for the STORM project page. Depends on core.js + data.js.
(function () {
  const D = window.STORM_DATA;
  const { METHODS, METHOD_KEYS, el, text, barPath, hover, swatchRow, segmented, sortableTable, groupedBars, hbarList } = window.SV;
  const $ = id => document.getElementById(id);
  const MODELS = [
    { value: "sonnet", label: "Sonnet 4.6" },
    { value: "qwen", label: "Qwen 3.6 Plus" },
    { value: "deepseek", label: "DeepSeek V4 Pro" },
  ];
  const f1 = v => (v == null ? "–" : v.toFixed(1));
  const f2 = v => (v == null ? "–" : v.toFixed(2));

  // ---------- Mean ± std bar charts (headline + judge swap) ----------
  function errorBars(svg, { title, rows, yMax, unit }) {
    const W = 440, H = 262, L = 40, R = 12, T = 34, B = 36;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const plotW = W - L - R, plotH = H - T - B, top = yMax * 1.1, y = v => T + plotH - (v / top) * plotH;
    text(svg, 0, 16, title, { "font-size": 14, "font-weight": 700, fill: "var(--text-primary)" });
    [0, 25, 50, 75, 100].forEach(t => {
      el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: "var(--line)" }, svg);
      text(svg, L - 8, y(t) + 4, t, { "text-anchor": "end" });
    });
    const band = plotW / rows.length, barW = 24;
    rows.forEach((r, i) => {
      const m = METHODS[r.key], cx = L + band * i + band / 2, g = el("g", { class: "mark" }, svg);
      el("path", { d: barPath(cx - barW / 2, y(r.mean), barW, y(0) - y(r.mean), 4), fill: m.color }, g);
      const lo = Math.max(0, r.mean - r.sd), hi = r.mean + r.sd;
      el("line", { x1: cx, x2: cx, y1: y(hi), y2: y(lo), stroke: "var(--text-secondary)", "stroke-width": 1.5 }, g);
      [hi, lo].forEach(v => el("line", { x1: cx - 5, x2: cx + 5, y1: y(v), y2: y(v), stroke: "var(--text-secondary)", "stroke-width": 1.5 }, g));
      text(g, cx, y(hi) - 6, r.mean.toFixed(1), { "text-anchor": "middle", "font-size": 12.5, "font-weight": 600, fill: "var(--text-primary)" });
      text(svg, cx, H - 10, m.name, { "text-anchor": "middle", "font-size": 12.5, "font-weight": 500, fill: "var(--text-secondary)" });
      const hit = el("rect", { x: cx - band / 2 + 4, y: T, width: band - 8, height: plotH, fill: "transparent" }, svg);
      hover(hit, `<div class="tt-h">${m.name}</div>${title}: ${r.mean.toFixed(2)} ± ${r.sd.toFixed(2)}${unit || ""}<br>3 independent evaluations`,
        () => { svg.classList.add("dim"); g.classList.add("hot"); }, () => { svg.classList.remove("dim"); g.classList.remove("hot"); });
    });
  }

  function headline() {
    errorBars($("panel-w"), { title: "Weighted pass rate, %", yMax: 100, rows: [
      { key: "single", mean: 21.70, sd: 1.41 }, { key: "worktree", mean: 25.11, sd: 0.71 }, { key: "storm", mean: 46.40, sd: 0.28 }] });
    errorBars($("panel-m"), { title: "Macro pass rate, %", yMax: 100, rows: [
      { key: "single", mean: 69.90, sd: 4.95 }, { key: "worktree", mean: 66.30, sd: 3.53 }, { key: "storm", mean: 82.29, sd: 0.30 }] });
    errorBars($("panel-judge"), { title: "PaperBench Code-Dev score (GPT-5.5 judge)", yMax: 100, rows: [
      { key: "single", mean: 65.71, sd: 2.74 }, { key: "worktree", mean: 67.74, sd: 0.95 }, { key: "storm", mean: 72.27, sd: 2.28 }] });
  }

  // ---------- Cross-model table (arXiv v1, Table 1) ----------
  const TABLE1 = {
    sonnet: [
      ["single", 20.7, 66.4, 3.2, 68.7, 12.5], ["worktree", 24.6, 63.8, 8.6, 72.7, 17.2], ["storm", 46.2, 82.5, 6.3, 74.1, 12.6],
      ["worktree+", 31.4, 78.6, 8.1, 76.6, 22.7], ["storm+", 49.2, 87.6, 6.3, 78.2, 17.3]],
    qwen: [
      ["single", 34.0, 75.3, 1.3, 47.7, 4.9], ["worktree", 16.7, 57.4, 6.9, 51.6, 13.4], ["storm", 61.4, 70.5, 2.5, 55.0, 8.2],
      ["worktree+", 36.3, 83.0, 3.7, 55.4, 12.1], ["storm+", 76.2, 88.2, 2.1, 57.0, 10.7]],
    deepseek: [
      ["single", 26.8, 65.2, 1.8, 62.9, 4.1], ["worktree", 18.5, 44.0, 3.8, 55.8, 8.8], ["storm", 32.3, 63.2, 3.0, 66.5, 9.7],
      ["worktree+", 30.9, 75.2, 3.8, 60.8, 9.1], ["storm+", 41.3, 77.7, 3.4, 68.3, 10.9]],
  };

  function crossModel() {
    const root = $("cross-model"), controls = root.querySelector(".controls"), holder = root.querySelector(".tbl-wrap");
    let model = "sonnet", withSel = false;
    const higher = [true, true, false, true, false];

    function rowsFor() {
      return TABLE1[model].filter(r => withSel || !r[0].endsWith("+")).map(r => ({
        key: r[0], sel: r[0].endsWith("+"), vals: r.slice(1),
        name: r[0].endsWith("+") ? `${METHODS[r[0].slice(0, -1)].name} + Single (select)` : METHODS[r[0]].name,
      }));
    }
    function draw() {
      const rows = rowsFor(), standalone = rows.filter(r => !r.sel);
      const best = higher.map((hb, c) => (hb ? Math.max : Math.min)(...standalone.map(r => r.vals[c])));
      const numCol = (label, c) => ({
        label, num: true, get: r => r.vals[c], fmt: v => f1(v),
        cls: r => (!r.sel && r.vals[c] === best[c] ? "win" : ""),
      });
      sortableTable(holder, {
        rows,
        rowClass: r => (r.key === "storm" ? "ours" : r.sel ? "sel" : ""),
        columns: [
          { label: "Method", get: r => r.name, fmt: (v, r) => `<span class="sw" style="background:${METHODS[r.key.replace("+", "")].color}"></span>${v}` },
          numCol("Commit0 Score<sub>w</sub> ↑", 0), numCol("Commit0 Score ↑", 1), numCol("Commit0 Cost<sub>eff</sub> ↓", 2),
          numCol("PaperBench Score ↑", 3), numCol("PaperBench Cost<sub>eff</sub> ↓", 4),
        ],
      });
    }
    const g1 = document.createElement("div"); g1.className = "group"; g1.innerHTML = "<span>Agent model</span>";
    segmented(g1, MODELS, model, v => { model = v; draw(); });
    const g2 = document.createElement("label"); g2.className = "chk";
    g2.innerHTML = `<input type="checkbox"> Show verifier-selected rows (+ Single)`;
    g2.querySelector("input").addEventListener("change", e => { withSel = e.target.checked; draw(); });
    controls.append(g1, g2);
    draw();
  }

  // ---------- Per-repository / per-paper explorer ----------
  function explorer() {
    const root = $("explorer");
    const controls = root.querySelector(".controls"), svg = root.querySelector("svg"),
      tableBox = root.querySelector(".tbl-scroll"), summary = root.querySelector(".summary-line");
    const state = { bench: "commit0", model: "sonnet", sort: "name", view: "chart" };
    const byName = (a, b) => a.name.localeCompare(b.name);
    const desc = f => (a, b) => (f(b) - f(a)) || byName(a, b);
    const SORTS = {
      name: { label: "Name (A–Z)", fn: byName },
      storm: { label: "STORM score (high → low)", fn: desc(r => r.storm.score) },
      gap: { label: "STORM gain over GitWorktree", fn: desc(r => r.storm.score - r.worktree.score) },
      gapSingle: { label: "STORM gain over Single-Agent", fn: desc(r => r.storm.score - r.single.score) },
    };

    function addGroup(label, node) {
      const g = document.createElement("div"); g.className = "group";
      g.innerHTML = `<span>${label}</span>`; g.appendChild(node); controls.appendChild(g); return g;
    }
    const benchBox = document.createElement("div"), modelBox = document.createElement("div"), viewBox = document.createElement("div");
    segmented(benchBox, [{ value: "commit0", label: "Commit0-Lite" }, { value: "paperbench", label: "PaperBench Code-Dev" }], state.bench,
      v => { state.bench = v; draw(); });
    segmented(modelBox, MODELS, state.model, v => { state.model = v; draw(); });
    const sel = document.createElement("select"); sel.className = "ctl";
    sel.innerHTML = Object.entries(SORTS).map(([k, s]) => `<option value="${k}">${s.label}</option>`).join("");
    sel.addEventListener("change", () => { state.sort = sel.value; draw(); });
    segmented(viewBox, [{ value: "chart", label: "Chart" }, { value: "table", label: "Table" }], state.view, v => { state.view = v; draw(); });
    addGroup("Benchmark", benchBox.firstChild); addGroup("Agent model", modelBox.firstChild);
    const sortGroup = addGroup("Sort by", sel); addGroup("View", viewBox.firstChild);

    function unitFor() { return state.bench === "commit0" ? "pass rate" : "judge score"; }
    function tipFor(r) {
      const rows = METHOD_KEYS.map(k => {
        const m = r[k];
        const extra = m.cost == null ? "no run recorded" : `$${m.cost.toFixed(2)} · ${Math.round(m.time / 60)} min`;
        return swatchRow(METHODS[k].color, METHODS[k].name, `<b>${f1(m.score)}</b> <span style="opacity:.7">${extra}</span>`);
      }).join("");
      return `<div class="tt-h">${r.name}</div>${rows}`;
    }

    function drawChart(rows) {
      svg.innerHTML = "";
      const rowH = 26, L = 240, R = 16, T = 26, W = 820, H = T + rows.length * rowH + 8;
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      const x = v => L + (v / 100) * (W - L - R);
      [0, 25, 50, 75, 100].forEach(t => {
        el("line", { x1: x(t), x2: x(t), y1: T - 6, y2: H - 4, stroke: "var(--line)" }, svg);
        text(svg, x(t), T - 12, t, { "text-anchor": "middle", "font-size": 11 });
      });
      text(svg, L - 12, T - 12, `${unitFor()} (%)`, { "text-anchor": "end", "font-size": 11 });
      rows.forEach((r, i) => {
        const cy = T + i * rowH + rowH / 2, g = el("g", { class: "mark" }, svg);
        const band = el("rect", { x: 0, y: cy - rowH / 2, width: W, height: rowH, fill: "transparent" }, g);
        const label = r.name.length > 34 ? r.name.slice(0, 32) + "…" : r.name;
        text(g, L - 12, cy + 4, label, { "text-anchor": "end", "font-size": 12.5, fill: "var(--text-secondary)", "font-family": "var(--mono)" });
        const vals = METHOD_KEYS.map(k => r[k].score).filter(v => v != null);
        el("line", { x1: x(Math.min(...vals)), x2: x(Math.max(...vals)), y1: cy, y2: cy, stroke: "var(--text-muted)", "stroke-width": 2, "stroke-linecap": "round", opacity: 0.5 }, g);
        ["single", "worktree", "storm"].forEach(k => {
          if (r[k].score == null) return;
          el("circle", { cx: x(r[k].score), cy, r: k === "storm" ? 6 : 5, fill: METHODS[k].color, stroke: "var(--surface-1)", "stroke-width": 2 }, g);
        });
        const hit = el("rect", { x: 0, y: cy - rowH / 2, width: W, height: rowH, fill: "transparent" }, g);
        hover(hit, () => tipFor(r), () => { band.setAttribute("fill", "var(--surface-2)"); }, () => { band.setAttribute("fill", "transparent"); });
      });
    }

    function drawTable(rows) {
      const best = r => Math.max(...METHOD_KEYS.map(k => r[k].score ?? -1));
      const cols = [{ label: state.bench === "commit0" ? "Repository" : "Paper", get: r => r.name, fmt: v => `<code>${v}</code>` }];
      METHOD_KEYS.forEach(k => {
        cols.push({ label: `${METHODS[k].name}`, num: true, get: r => r[k].score, fmt: v => f1(v), cls: r => (r[k].score === best(r) ? "win" : "") });
        cols.push({ label: "$", num: true, get: r => r[k].cost, fmt: v => (v == null ? "–" : v.toFixed(1)) });
      });
      cols.push({ label: "Δ vs GitWorktree", num: true, get: r => r.storm.score - r.worktree.score, fmt: v => (v > 0 ? "+" : "") + v.toFixed(1) });
      sortableTable(tableBox, { columns: cols, rows: rows.slice().sort(byName), sort: { index: 0, dir: "asc" } });
    }

    function draw() {
      const rows = D.perInstance[state.bench][state.model].slice().sort(SORTS[state.sort].fn);
      const n = rows.length;
      const wins = k => rows.filter(r => r[k].score === Math.max(...METHOD_KEYS.map(m => r[m].score ?? -1))).length;
      const mean = k => rows.reduce((s, r) => s + (r[k].score ?? 0), 0) / n;
      summary.innerHTML = `${n} ${state.bench === "commit0" ? "repositories" : "papers"} · best or tied-best on: ` +
        METHOD_KEYS.map(k => `<b>${METHODS[k].name}</b> ${wins(k)}`).join(" · ") +
        ` · macro mean: ` + METHOD_KEYS.map(k => `${METHODS[k].name} ${mean(k).toFixed(1)}`).join(" / ");
      sortGroup.style.display = state.view === "chart" ? "" : "none";
      svg.parentElement.style.display = state.view === "chart" ? "" : "none";
      tableBox.style.display = state.view === "table" ? "" : "none";
      if (state.view === "chart") drawChart(rows); else drawTable(rows);
    }
    draw();
  }

  // ---------- Coupling analysis (Fig. 3, rebuilt) ----------
  function coupling() {
    const C = D.coupling;
    const PRE = { key: "pre", name: "Pre-commit (write time)", color: "#4a3aa7" };
    const POST = { key: "post", name: "Post-commit (merge)", color: "#eda100" };
    groupedBars($("coupling-a"), {
      categories: C.conflicts.map(c => c.config.replace(" (k=4)", "").replace("GitWorktree", "Worktree")), series: [PRE, POST], yMax: 3.5, ticks: [0, 1, 2, 3],
      value: (ci, k) => C.conflicts[ci][k], labelAll: true, fmt: v => (v ? v.toFixed(2) : ""), bottom: 44,
      subLabel: ci => `pass ${C.conflicts[ci].pass.toFixed(1)}%`,
      tipHtml: ci => { const c = C.conflicts[ci]; return `<div class="tt-h">${c.config}</div>` +
        swatchRow(PRE.color, "Pre-commit conflicts / run", c.pre.toFixed(2)) + swatchRow(POST.color, "Post-commit conflicts / run", c.post.toFixed(2)) +
        `Final pass rate ${c.pass.toFixed(1)}%`; },
    });
    const series = METHOD_KEYS.map(k => ({ key: k, name: METHODS[k].name, color: METHODS[k].color }));
    groupedBars($("coupling-b"), {
      categories: C.strata.map(s => s.stratum), series, yMax: 100, ticks: [0, 25, 50, 75, 100],
      value: (ci, k) => C.strata[ci][k], labelKey: "storm", fmt: f1, reserveSub: true,
      tipHtml: ci => { const s = C.strata[ci]; return `<div class="tt-h">${s.stratum}-coupling repositories</div>` +
        series.map(m => swatchRow(m.color, m.name, f1(s[m.key]) + "%")).join("") +
        `STORM − GitWorktree: +${(s.storm - s.worktree).toFixed(1)}`; },
    });
    const OV = { key: "overlap", name: "First-round scope overlap", color: "#e87ba4" };
    const DEP = { key: "dependency", name: "Dependency signal", color: "#008300" };
    groupedBars($("coupling-c"), {
      categories: C.scopes.map(s => `${s.agents} agents`), series: [OV, DEP], yMax: 70, ticks: [0, 20, 40, 60],
      value: (ci, k) => C.scopes[ci][k], labelAll: true, fmt: f1, reserveSub: true,
      tipHtml: ci => { const s = C.scopes[ci]; return `<div class="tt-h">k = ${s.agents}</div>` +
        swatchRow(OV.color, OV.name, f1(s.overlap) + "%") + swatchRow(DEP.color, DEP.name, f1(s.dependency) + "%"); },
    });
  }

  // ---------- jinja case study: paired timelines (Fig. 4, rebuilt) ----------
  const KINDS = {
    assign: { name: "Assignment", color: "#e87ba4" },
    "assign-coupled": { name: "Coupling-aware assignment", color: "#eda100" },
    work: { name: "Engineer work", color: "#2a78d6" },
  };

  function gantt(svg, run, tMax, title) {
    svg.innerHTML = "";
    const rowH = 30, L = 76, R = 14, T = 30, W = 820, H = T + run.rows.length * rowH + 34;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const x = t => L + (t / tMax) * (W - L - R), rowY = name => T + run.rows.indexOf(name) * rowH;
    text(svg, 0, 16, title, { "font-size": 14, "font-weight": 600, fill: "var(--text-primary)" });
    for (let t = 0; t <= tMax; t += 5) {
      el("line", { x1: x(t), x2: x(t), y1: T - 4, y2: H - 30, stroke: "var(--line)" }, svg);
      text(svg, x(t), H - 14, t, { "text-anchor": "middle", "font-size": 11 });
    }
    text(svg, W - R, H - 1, "minutes since first relevant event", { "text-anchor": "end", "font-size": 11 });
    if (run.rework) {
      const band = el("rect", { x: x(run.rework[0]), y: T - 4, width: x(run.rework[1]) - x(run.rework[0]), height: run.rows.length * rowH, fill: "#e34948", opacity: 0.08 }, svg);
      hover(band, `<div class="tt-h">Rework window</div>${run.rework[0].toFixed(1)}–${run.rework[1].toFixed(1)} min: the focus task is redone after a merge-conflict rejection`);
    }
    run.rows.forEach(name => text(svg, L - 10, rowY(name) + rowH / 2 + 4, name, { "text-anchor": "end", "font-size": 12.5, fill: "var(--text-secondary)" }));
    run.segments.forEach(s => {
      const k = KINDS[s.kind], y0 = rowY(s.row) + 6, w = Math.max(2, x(s.t1) - x(s.t0));
      const rect = el("rect", { class: "mark", x: x(s.t0), y: y0, width: w, height: rowH - 12, rx: 3, fill: k.color,
        stroke: s.focus ? "var(--text-primary)" : "var(--surface-1)", "stroke-width": s.focus ? 2 : 1 }, svg);
      if (s.label && w > 40) text(svg, x(s.t0) + w / 2, y0 + (rowH - 12) / 2 + 4, s.label,
        { "text-anchor": "middle", "font-size": 11, fill: "#fff", "font-weight": 600, "pointer-events": "none" });
      hover(rect, `<div class="tt-h">${s.row} · ${s.label || k.name}</div>${k.name}${s.focus ? " (focus task)" : ""}<br>` +
        `${s.t0.toFixed(1)}–${s.t1.toFixed(1)} min (${(s.t1 - s.t0).toFixed(1)} min)`);
    });
    run.reviews.forEach(r => {
      const cx = x(r.t), cy = rowY("Manager") + rowH / 2, s = r.ok ? 7 : 9;
      const g = el("g", { class: "mark" }, svg);
      if (r.ok) el("path", { d: `M${cx},${cy - s} L${cx + s},${cy} L${cx},${cy + s} L${cx - s},${cy} Z`, fill: "#008300", stroke: "var(--surface-1)", "stroke-width": 2 }, g);
      else el("circle", { cx, cy, r: 8, fill: "#e34948", stroke: "var(--surface-1)", "stroke-width": 2 }, g);
      if (!r.ok) el("path", { d: `M${cx - 3.5},${cy - 3.5} L${cx + 3.5},${cy + 3.5} M${cx + 3.5},${cy - 3.5} L${cx - 3.5},${cy + 3.5}`, stroke: "#fff", "stroke-width": 2, "stroke-linecap": "round" }, g);
      el("circle", { cx, cy, r: 12, fill: "transparent" }, g);
      hover(g, `<div class="tt-h">Manager review · ${r.ok ? "accepted" : "rejected"}</div>${r.note || ""}${r.note ? "<br>" : ""}t = ${r.t.toFixed(1)} min`);
    });
  }

  function jinja() {
    const J = D.jinja, box = $("jinja"), controls = box.querySelector(".controls");
    let shared = true;
    const draw = () => {
      gantt($("gantt-worktree"), J.worktree, 40, "GitWorktree: coupling surfaces at merge review");
      gantt($("gantt-storm"), J.storm, shared ? 40 : 25, "STORM: coupling handled at decomposition time");
    };
    const g = document.createElement("div"); g.className = "group"; g.innerHTML = "<span>Time axis</span>";
    segmented(g, [{ value: "shared", label: "Shared (0–40 min)" }, { value: "fit", label: "Fit each run" }], "shared",
      v => { shared = v === "shared"; draw(); });
    controls.appendChild(g);
    draw();
  }

  // ---------- Scaling engineers (Fig. 2, rebuilt; linked hover) ----------
  function scaling() {
    const P = D.scaling.points, cats = P.map(p => (p.max === 1 ? "1 (single)" : String(p.max)));
    const colorAt = ci => (P[ci].max === 1 ? METHODS.single.color : METHODS.storm.color);
    const charts = [];
    const link = ci => charts.forEach(c => c.highlight(ci));
    const tipFor = ci => { const p = P[ci]; return `<div class="tt-h">Max engineers = ${p.max}${p.max === 1 ? " (single agent)" : ""}</div>` +
      `Weighted ${f1(p.weighted)}% · Macro ${f1(p.macro)}%<br>Avg engineers deployed ${p.deployed.toFixed(1)}<br>` +
      `$${p.cost.toFixed(1)} / repo · ${p.time.toFixed(1)} min / repo`; };
    charts.push(groupedBars($("scale-a"), {
      categories: cats, yMax: 100, ticks: [0, 25, 50, 75, 100], labelAll: true, fmt: f1, bottom: 44,
      series: [{ key: "weighted", name: "Weighted", color: "#0f7a55" }, { key: "macro", name: "Macro", color: "#1baf7a" }],
      color: (ci, s) => (P[ci].max === 1 ? (s.key === "weighted" ? "#1c5cab" : "#2a78d6") : s.color),
      value: (ci, k) => P[ci][k], subLabel: ci => `${P[ci].deployed.toFixed(1)} eng`, tipHtml: tipFor, onHover: link,
    }));
    charts.push(groupedBars($("scale-b"), {
      categories: cats, yMax: 30, ticks: [0, 10, 20, 30], labelAll: true, fmt: v => "$" + v.toFixed(1),
      series: [{ key: "cost", name: "Cost", color: METHODS.storm.color }], color: colorAt, reserveSub: true,
      value: (ci, k) => P[ci][k], tipHtml: tipFor, onHover: link,
    }));
    charts.push(groupedBars($("scale-c"), {
      categories: cats, yMax: 60, ticks: [0, 20, 40, 60], labelAll: true, fmt: f1,
      series: [{ key: "time", name: "Time", color: METHODS.storm.color }], color: colorAt, reserveSub: true,
      value: (ci, k) => P[ci][k], tipHtml: tipFor, onHover: link,
    }));
  }

  // ---------- Ablations + coordination baselines ----------
  function baselines() {
    const BASE = [
      { label: "Shared memory (MARBLE-based)", w: 13.47, m: 45.71 },
      { label: "CRDT (CodeCRDT-based)", w: 13.13, m: 50.36 },
      { label: "GitWorktree", w: 25.11, m: 66.30, color: METHODS.worktree.color },
      { label: "STORM", w: 46.40, m: 82.29, strong: true },
    ];
    const box = $("baselines");
    let metric = "w";
    const name = () => (metric === "w" ? "Weighted pass rate" : "Macro pass rate");
    const rows = () => BASE.map(r => ({ ...r, value: r[metric], color: r.strong ? METHODS.storm.color : r.color || "#9b9990" }));
    const tipHtml = r => {
      const storm = BASE.find(x => x.strong)[metric];
      return `<div class="tt-h">${r.label}</div>${name()}: ${r.value.toFixed(2)}%` +
        (r.strong ? "" : `<br>vs STORM: ${(r.value - storm).toFixed(2)} points`);
    };
    const draw = () => hbarList($("base-chart"), { rows: rows(), max: 100, fmt: f2, tipHtml });
    const g = document.createElement("div"); g.className = "group"; g.innerHTML = "<span>Metric</span>";
    segmented(g, [{ value: "w", label: "Score<sub>w</sub> (weighted)" }, { value: "m", label: "Score (macro)" }], "w", v => { metric = v; draw(); });
    box.querySelector(".controls").appendChild(g);
    draw();
  }

  document.addEventListener("DOMContentLoaded", () => {
    headline(); crossModel(); explorer(); coupling(); jinja(); scaling(); baselines();
  });
})();
