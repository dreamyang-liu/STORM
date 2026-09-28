// Shared chart + table primitives for the STORM project page. No dependencies.
(function () {
  const NS = "http://www.w3.org/2000/svg";

  const METHODS = {
    single:   { name: "Single-Agent", color: "var(--series-1)" },
    worktree: { name: "GitWorktree",  color: "var(--series-2)" },
    storm:    { name: "STORM",        color: "var(--series-3)" },
  };
  const METHOD_KEYS = ["single", "worktree", "storm"];

  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    for (const k in attrs || {}) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function text(parent, x, y, str, attrs) {
    const t = el("text", Object.assign({ x, y, "font-size": 12, fill: "var(--text-muted)" }, attrs || {}), parent);
    t.textContent = str;
    return t;
  }

  // Vertical bar: 4px rounded data-end, square at the baseline.
  function barPath(x, y, w, h, r) {
    if (h <= 0) return "";
    r = Math.min(r, h, w / 2);
    return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
  }

  // Horizontal bar: rounded right end, square at the baseline (left).
  function hbarPath(x, y, w, h, r) {
    if (w <= 0) return "";
    r = Math.min(r, w, h / 2);
    return `M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z`;
  }

  // ---------- Tooltip (one per page, fixed-positioned) ----------
  const tipNode = document.createElement("div");
  tipNode.className = "tooltip";
  tipNode.setAttribute("role", "status");
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(tipNode));

  const tip = {
    show(evt, html) {
      tipNode.innerHTML = html;
      tipNode.style.opacity = 1;
      const pad = 14, box = tipNode.getBoundingClientRect();
      let x = evt.clientX + pad, y = evt.clientY - box.height - 8;
      if (x + box.width > window.innerWidth - 8) x = evt.clientX - box.width - pad;
      if (y < 8) y = evt.clientY + pad;
      tipNode.style.left = x + "px";
      tipNode.style.top = y + "px";
    },
    hide() { tipNode.style.opacity = 0; },
  };

  function swatchRow(color, label, value) {
    return `<div class="tt-row"><i style="background:${color}"></i>${label}<span style="margin-left:auto;padding-left:12px">${value}</span></div>`;
  }

  // Attach hover to a node; html may be a string or a function returning one.
  function hover(node, html, onEnter, onLeave) {
    node.addEventListener("mousemove", e => tip.show(e, typeof html === "function" ? html() : html));
    node.addEventListener("mouseenter", () => onEnter && onEnter());
    node.addEventListener("mouseleave", () => { tip.hide(); onLeave && onLeave(); });
  }

  // ---------- Segmented control ----------
  // options: [{value, label}], returns {set(value)}
  function segmented(container, options, initial, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "seg";
    wrap.setAttribute("role", "group");
    const buttons = options.map(opt => {
      const b = document.createElement("button");
      b.type = "button";
      b.innerHTML = opt.label;
      b.dataset.value = opt.value;
      b.addEventListener("click", () => set(opt.value, true));
      wrap.appendChild(b);
      return b;
    });
    function set(value, fire) {
      buttons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.value === String(value))));
      if (fire) onChange(value);
    }
    set(initial, false);
    container.appendChild(wrap);
    return { set };
  }

  // ---------- Sortable table ----------
  // columns: [{key, label, get(row) -> value, fmt(value,row) -> html, num: bool, cls(row) -> string}]
  function sortableTable(container, { columns, rows, rowClass, sort }) {
    container.innerHTML = "";
    const table = document.createElement("table");
    const thead = table.createTHead().insertRow();
    const tbody = table.createTBody();
    let state = sort ? { ...sort } : null;

    columns.forEach((col, i) => {
      const th = document.createElement("th");
      th.innerHTML = col.label;
      if (col.sortable !== false) {
        th.className = "sortable";
        th.tabIndex = 0;
        const toggle = () => {
          state = state && state.index === i
            ? { index: i, dir: state.dir === "desc" ? "asc" : "desc" }
            : { index: i, dir: col.num ? "desc" : "asc" };
          render();
        };
        th.addEventListener("click", toggle);
        th.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
      }
      thead.appendChild(th);
    });

    function render() {
      const sorted = rows.slice();
      if (state) {
        const col = columns[state.index], sign = state.dir === "asc" ? 1 : -1;
        sorted.sort((a, b) => {
          const va = col.get(a), vb = col.get(b);
          if (va == null) return 1;
          if (vb == null) return -1;
          return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * sign;
        });
      }
      [...thead.children].forEach((th, i) =>
        th.setAttribute("aria-sort", state && state.index === i ? (state.dir === "asc" ? "ascending" : "descending") : "none"));
      tbody.innerHTML = sorted.map(row => {
        const cls = rowClass ? rowClass(row) : "";
        const cells = columns.map(col => {
          const v = col.get(row);
          const html = col.fmt ? col.fmt(v, row) : (v == null ? "–" : v);
          const c = col.cls ? col.cls(row, v) : "";
          return `<td${c ? ` class="${c}"` : ""}>${html}</td>`;
        }).join("");
        return `<tr${cls ? ` class="${cls}"` : ""}>${cells}</tr>`;
      }).join("");
    }

    render();
    container.appendChild(table);
    return { update(newRows) { rows = newRows; render(); } };
  }

  // ---------- Grouped vertical bars ----------
  // opts: {categories:[label], series:[{key,name,color}], value(catIndex, key), yMax, ticks, fmt, tipHtml(ci)}
  function groupedBars(svg, opts) {
    svg.innerHTML = "";
    const W = opts.width || 300, H = opts.height || 210, L = 34, R = 6, T = 22, B = opts.bottom || 30;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const plotW = W - L - R, plotH = H - T - B;
    const y = v => T + plotH - (v / opts.yMax) * plotH;

    opts.ticks.forEach(t => {
      el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: "var(--line)", "stroke-width": 1 }, svg);
      text(svg, L - 6, y(t) + 4, t, { "text-anchor": "end", "font-size": 11 });
    });

    const nC = opts.categories.length, nS = opts.series.length;
    const band = plotW / nC, barW = Math.min(opts.barW || 22, (band - 16) / nS - 2);
    const groups = [];
    opts.categories.forEach((cat, ci) => {
      const cx = L + band * ci + band / 2;
      const g = el("g", { class: "mark" }, svg);
      groups.push(g);
      const x0 = cx - (nS * barW + (nS - 1) * 2) / 2;
      opts.series.forEach((s, si) => {
        const v = opts.value(ci, s.key);
        if (v == null) return;
        const x = x0 + si * (barW + 2);
        el("path", { d: barPath(x, y(v), barW, y(0) - y(v), 4), fill: opts.color ? opts.color(ci, s) : s.color }, g);
        if (opts.labelAll || (opts.labelKey && s.key === opts.labelKey)) {
          text(g, x + barW / 2, y(v) - 5, opts.fmt ? opts.fmt(v) : v,
            { "text-anchor": "middle", "font-size": 11, "font-weight": 600, fill: "var(--text-primary)" });
        }
      });
      text(svg, cx, H - B + 17, cat, { "text-anchor": "middle", "font-size": 12, fill: "var(--text-secondary)" });
      if (opts.subLabel) text(svg, cx, H - B + 30, opts.subLabel(ci), { "text-anchor": "middle", "font-size": 11 });
      const hit = el("rect", { x: cx - band / 2 + 2, y: T - 10, width: band - 4, height: plotH + 10, fill: "transparent" }, svg);
      hover(hit, () => opts.tipHtml(ci),
        () => { svg.classList.add("dim"); g.classList.add("hot"); if (opts.onHover) opts.onHover(ci); },
        () => { svg.classList.remove("dim"); g.classList.remove("hot"); if (opts.onHover) opts.onHover(null); });
    });
    return {
      highlight(ci) {
        svg.classList.toggle("dim", ci != null);
        groups.forEach((g, i) => g.classList.toggle("hot", i === ci));
      },
    };
  }

  // ---------- Horizontal bar list ----------
  // rows: [{label, value, color, note}], max, fmt
  function hbarList(svg, { rows, max, fmt, tipHtml }) {
    svg.innerHTML = "";
    const rowH = 34, L = 214, R = 44, W = 480, H = rows.length * rowH + 8;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const x = v => (v / max) * (W - L - R);
    rows.forEach((r, i) => {
      const yTop = 4 + i * rowH;
      const g = el("g", { class: "mark" }, svg);
      text(g, L - 10, yTop + rowH / 2 + 4, r.label,
        { "text-anchor": "end", "font-size": 13, fill: r.strong ? "var(--text-primary)" : "var(--text-secondary)", "font-weight": r.strong ? 700 : 400 });
      el("rect", { x: L, y: yTop + 8, width: W - L - R, height: rowH - 16, fill: "var(--surface-2)", rx: 3 }, g);
      el("path", { d: hbarPath(L, yTop + 8, x(r.value), rowH - 16, 4), fill: r.color }, g);
      text(g, L + x(r.value) + 6, yTop + rowH / 2 + 4, fmt(r.value),
        { "font-size": 12.5, "font-weight": 600, fill: "var(--text-primary)" });
      const hit = el("rect", { x: 0, y: yTop, width: W, height: rowH, fill: "transparent" }, svg);
      hover(hit, () => tipHtml(r), () => { svg.classList.add("dim"); g.classList.add("hot"); },
        () => { svg.classList.remove("dim"); g.classList.remove("hot"); });
    });
  }

  window.SV = { METHODS, METHOD_KEYS, el, text, barPath, hbarPath, tip, hover, swatchRow, segmented, sortableTable, groupedBars, hbarList };
})();
