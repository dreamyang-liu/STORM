// Interactive framework diagram: a scripted walk-through of one STORM episode.
// Illustrative scenario (not run data). Depends on core.js.
(function () {
  const { el, text, hover } = window.SV;
  const W = 1000, H = 560;
  const C = {
    read: "#2a78d6", write: "#1baf7a", reject: "#e34948", ok: "#008300", bad: "#e34948",
    ink: "var(--text-primary)", ink2: "var(--text-secondary)", muted: "var(--text-muted)",
    line: "var(--line-strong)", accent: "var(--accent)",
  };
  const FILES = [
    { id: "utils", name: "utils.py", x: 230 },
    { id: "core", name: "core.py", x: 500 },
    { id: "models", name: "models.py", x: 770 },
  ];
  const ENGS = [
    { id: "E1", name: "Engineer 1", x: 230, file: "utils" },
    { id: "E2", name: "Engineer 2", x: 500, file: "core" },
    { id: "E3", name: "Engineer 3", x: 770, file: "models" },
  ];
  const Y = { mgrTop: 18, mgrBot: 86, engTop: 136, engBot: 250, bandTop: 290, bandMid: 330, bandBot: 372, fileTop: 424, fileBot: 522 };
  const STAGES = ["Reservation", "Version", "Snapshot"];
  const fileById = id => FILES.find(f => f.id === id);
  const engById = id => ENGS.find(e => e.id === id);

  function initialState() {
    return {
      files: { utils: { v: 3, by: "—" }, core: { v: 8, by: "—" }, models: { v: 5, by: "—" } },
      locks: {},
      engs: Object.fromEntries(ENGS.map(e => [e.id, { task: null, snap: [], status: "idle", kind: null }])),
      storm: { msg: "Waiting for file operations", kind: null, stages: [null, null, null] },
      mgr: { msg: "Scans the repository and plans the work", kind: null },
      delegated: false, committed: false,
    };
  }

  // ---------- Scenario ----------
  const STEPS = [
    { title: "Shared workspace", text: "All engineers work in <b>one</b> workspace. Every file carries a monotonically increasing version.",
      run: async () => {} },
    { title: "Delegate", text: "The manager splits the task into scoped sub-tasks, one primary file per engineer. Scopes reduce contention but don't prevent it: engineers may still read other files.",
      run: async (S, A) => {
        S.mgr.msg = "Delegating scoped tasks"; S.delegated = true;
        ENGS.forEach(e => { S.engs[e.id].task = e.file; S.engs[e.id].status = "task assigned"; });
        A.render(); await A.pause(1200);
        S.mgr.msg = "Waiting for engineers";
      } },
    { title: "Read", text: "Every read goes through STORM, which records the file and version in the engineer's <b>read snapshot</b>. Engineer 2 also reads <code>utils.py</code>, because <code>core.py</code> depends on it.",
      run: async (S, A) => {
        await Promise.all([
          A.read(S, "E1", "utils"),
          (async () => { await A.read(S, "E2", "core"); await A.read(S, "E2", "utils"); })(),
          A.read(S, "E3", "models"),
        ]);
      } },
    { title: "Parallel writes", text: "Engineers 1 and 3 write their files. Nothing in their snapshots has changed, so both writes are accepted and the versions go up. Most work runs fully in parallel like this.",
      run: async (S, A) => {
        await Promise.all([A.write(S, "E1", "utils"), A.write(S, "E3", "models")]);
      } },
    { title: "Stale dependency", text: "Engineer 2 writes <code>core.py</code>, but it read <code>utils.py</code> at v3 and the file is now v4. STORM <b>rejects</b> the write and returns the current content, a diff, and the stale-dependency list. Engineer 2 gets a short reservation on <code>core.py</code>.",
      run: async (S, A) => { await A.write(S, "E2", "core", { failStage: 2, stale: "utils" }); } },
    { title: "Refresh & retry", text: "Engineer 2 re-reads <code>utils.py</code>, adapts <code>core.py</code> to the new interface, and writes again. The snapshot is current, so the write is accepted and the reservation is released.",
      run: async (S, A) => {
        await A.read(S, "E2", "utils");
        await A.write(S, "E2", "core");
      } },
    { title: "Review & commit", text: "The manager reviews the diffs, runs the tests, and commits. The conflict was resolved at write time, while Engineer 2 still had the context, not at a merge step afterwards.",
      run: async (S, A) => {
        S.mgr.msg = "Reviewing diffs and running tests"; A.render();
        await Promise.all(ENGS.map(e => A.travel([[e.x, Y.engTop], [e.x, Y.engTop - 22], [500, Y.engTop - 22], [500, Y.mgrBot]], C.write)));
        S.mgr.msg = "✓ Tests pass, changes committed"; S.mgr.kind = "ok"; S.committed = true;
        ENGS.forEach(e => { S.engs[e.id].status = "✓ done"; S.engs[e.id].kind = "ok"; });
      } },
  ];

  // ---------- Build static skeleton ----------
  function build(svg) {
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const defs = el("defs", {}, svg);
    const grad = el("linearGradient", { id: "fw-band", x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
    el("stop", { offset: "0%", "stop-color": "#e7f5ee" }, grad);
    el("stop", { offset: "100%", "stop-color": "#f1faf5" }, grad);
    const glow = el("filter", { id: "fw-glow", x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
    el("feGaussianBlur", { stdDeviation: 3.5 }, glow);

    const R = {};
    // Delegation links
    R.links = ENGS.map(e => el("path", {
      d: `M500,${Y.mgrBot} C500,${Y.mgrBot + 30} ${e.x},${Y.engTop - 30} ${e.x},${Y.engTop}`,
      class: "fw-link", fill: "none" }, svg));

    // Manager
    const mg = el("g", { class: "fw-node" }, svg);
    R.mgrBox = el("rect", { x: 330, y: Y.mgrTop, width: 340, height: Y.mgrBot - Y.mgrTop, rx: 14, class: "fw-box" }, mg);
    text(mg, 500, Y.mgrTop + 28, "Manager", { "text-anchor": "middle", "font-size": 16, "font-weight": 700, fill: C.ink });
    R.mgrMsg = text(mg, 500, Y.mgrTop + 51, "", { "text-anchor": "middle", "font-size": 13, fill: C.ink2 });
    hover(mg, `<div class="tt-h">Manager</div>Decomposes the task, assigns scoped sub-tasks, reviews diffs, runs tests.<br>It is the only agent that commits.`);

    // Engineers
    R.eng = {};
    ENGS.forEach(e => {
      const g = el("g", { class: "fw-node" }, svg);
      const box = el("rect", { x: e.x - 118, y: Y.engTop, width: 236, height: Y.engBot - Y.engTop, rx: 14, class: "fw-box" }, g);
      text(g, e.x - 102, Y.engTop + 25, e.name, { "font-size": 15, "font-weight": 700, fill: C.ink });
      const task = text(g, e.x + 102, Y.engTop + 25, "", { "text-anchor": "end", "font-size": 12, fill: C.muted, "font-family": "var(--mono)" });
      text(g, e.x - 102, Y.engTop + 48, "READ SNAPSHOT", { "font-size": 10, "font-weight": 700, "letter-spacing": ".08em", fill: C.muted });
      const chips = el("g", {}, g);
      const status = text(g, e.x - 102, Y.engBot - 14, "", { "font-size": 12.5, "font-weight": 600, fill: C.ink2 });
      R.eng[e.id] = { box, task, chips, status };
      hover(g, () => {
        const st = R.state.engs[e.id];
        const snap = st.snap.length ? st.snap.map(s => `<code style="background:rgba(255,255,255,.12);color:#fff">${fileById(s.f).name}@v${s.v}</code>`).join(" ") : "empty";
        return `<div class="tt-h">${e.name}</div>Works only through the STORM-mediated file editor.<br>Snapshot: ${snap}`;
      });
    });

    // STORM band
    const bg = el("g", { class: "fw-node" }, svg);
    R.band = el("rect", { x: 40, y: Y.bandTop, width: W - 80, height: Y.bandBot - Y.bandTop, rx: 16, fill: "url(#fw-band)", class: "fw-band" }, bg);
    el("image", { href: "static/logo.svg", x: 60, y: Y.bandTop + 12, width: 26, height: 26 }, bg);
    text(bg, 94, Y.bandTop + 31, "STORM", { "font-size": 16, "font-weight": 800, "letter-spacing": ".06em", fill: C.accent });
    text(bg, 168, Y.bandTop + 31, "mediates every read and write", { "font-size": 13, fill: C.ink2 });
    R.stormMsg = text(bg, W / 2, Y.bandBot - 12, "", { "text-anchor": "middle", "font-size": 13.5, "font-weight": 600, fill: C.ink2 });
    R.pills = STAGES.map((s, i) => {
      const x = 640 + i * 102;
      const r = el("rect", { x, y: Y.bandTop + 14, width: 94, height: 24, rx: 12, class: "fw-pill" }, bg);
      const t = text(bg, x + 47, Y.bandTop + 30, `${i + 1} ${s}`, { "text-anchor": "middle", "font-size": 11.5, "font-weight": 600, fill: C.ink2 });
      return { r, t };
    });
    hover(bg, `<div class="tt-h">STORM layer</div>On every write it checks, in order:<br>1. is the file reserved by another agent?<br>2. is the target file still at the version the agent read?<br>3. is every file in the agent's snapshot still current?<br>Reads never block.`);

    // Files
    R.file = {};
    const ws = el("g", {}, svg);
    el("rect", { x: 40, y: Y.fileTop - 20, width: W - 80, height: Y.fileBot - Y.fileTop + 34, rx: 18, class: "fw-ws" }, ws);
    text(ws, 60, Y.fileTop - 4, "SHARED WORKSPACE", { "font-size": 10.5, "font-weight": 700, "letter-spacing": ".1em", fill: C.muted });
    FILES.forEach(f => {
      const g = el("g", { class: "fw-node" }, svg);
      const box = el("rect", { x: f.x - 105, y: Y.fileTop + 8, width: 210, height: Y.fileBot - Y.fileTop - 8, rx: 12, class: "fw-file" }, g);
      el("path", { d: `M${f.x - 88},${Y.fileTop + 26} h12 l6,6 v16 h-18 z`, fill: "none", stroke: C.muted, "stroke-width": 1.4, "stroke-linejoin": "round" }, g);
      text(g, f.x - 64, Y.fileTop + 42, f.name, { "font-size": 14.5, "font-weight": 600, fill: C.ink, "font-family": "var(--mono)" });
      const badge = el("rect", { x: f.x + 46, y: Y.fileTop + 26, width: 44, height: 22, rx: 11, class: "fw-badge" }, g);
      const ver = text(g, f.x + 68, Y.fileTop + 41, "", { "text-anchor": "middle", "font-size": 12.5, "font-weight": 700, fill: C.accent });
      const by = text(g, f.x - 88, Y.fileTop + 76, "", { "font-size": 12, fill: C.muted });
      const lock = el("g", { opacity: 0 }, g);
      el("rect", { x: f.x + 60, y: Y.fileTop + 66, width: 14, height: 11, rx: 2, fill: C.reject }, lock);
      el("path", { d: `M${f.x + 63},${Y.fileTop + 66} v-4 a4,4 0 0 1 8,0 v4`, fill: "none", stroke: C.reject, "stroke-width": 1.8 }, lock);
      const lockT = text(lock, f.x - 88, Y.fileTop + 76, "", { "font-size": 12, "font-weight": 650, fill: C.reject });
      R.file[f.id] = { box, badge, ver, by, lock, lockT };
      hover(g, () => {
        const st = R.state.files[f.id], lk = R.state.locks[f.id];
        return `<div class="tt-h">${f.name} · v${st.v}</div>Last write: ${st.by}${lk ? `<br>Reserved by ${lk} after a rejected write (up to 30 s)` : ""}`;
      });
    });

    R.packets = el("g", { "pointer-events": "none" }, svg);
    return R;
  }

  // ---------- Render dynamic state ----------
  function render(R, S) {
    R.state = S;
    R.mgrMsg.textContent = S.mgr.msg;
    R.mgrMsg.setAttribute("fill", S.mgr.kind === "ok" ? C.ok : C.ink2);
    R.mgrBox.classList.toggle("ok", !!S.committed);
    R.links.forEach(l => l.classList.toggle("on", S.delegated));
    ENGS.forEach(e => {
      const st = S.engs[e.id], r = R.eng[e.id];
      r.task.textContent = st.task ? `task: ${fileById(st.task).name}` : "";
      r.status.textContent = st.status;
      r.status.setAttribute("fill", st.kind === "ok" ? C.ok : st.kind === "bad" ? C.bad : C.ink2);
      r.box.classList.toggle("bad", st.kind === "bad");
      r.chips.innerHTML = "";
      st.snap.forEach((s, i) => {
        const x = e.x - 102 + i * 108, y = Y.engTop + 56;
        const chip = el("g", { class: s.stale ? "fw-chip stale" : "fw-chip" }, r.chips);
        el("rect", { x, y, width: 100, height: 22, rx: 6 }, chip);
        text(chip, x + 50, y + 15, `${fileById(s.f).name} v${s.v}`, { "text-anchor": "middle", "font-size": 11.5, "font-family": "var(--mono)" });
      });
    });
    R.stormMsg.textContent = S.storm.msg;
    R.stormMsg.setAttribute("fill", S.storm.kind === "ok" ? C.ok : S.storm.kind === "bad" ? C.bad : C.ink2);
    R.band.classList.toggle("bad", S.storm.kind === "bad");
    R.pills.forEach((p, i) => { p.r.setAttribute("class", "fw-pill" + (S.storm.stages[i] ? " " + S.storm.stages[i] : "")); });
    FILES.forEach(f => {
      const st = S.files[f.id], r = R.file[f.id];
      r.ver.textContent = `v${st.v}`;
      const lk = S.locks[f.id];
      r.by.textContent = lk ? "" : `last write: ${st.by}`;
      r.lock.setAttribute("opacity", lk ? 1 : 0);
      r.lockT.textContent = lk ? `reserved by ${lk} (≤ 30 s)` : "";
    });
  }

  // ---------- Animation primitives ----------
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function makeAnim(R, S, ctl, instant) {
    const alive = () => ctl.token === ctl.current && !instant;
    const A = {
      render: () => render(R, S),
      pause: ms => (alive() ? new Promise(r => setTimeout(r, ms)) : Promise.resolve()),
      travel(pts, color) {
        if (!alive()) return Promise.resolve();
        const d = "M" + pts.map(p => p.join(",")).join(" L");
        const path = el("path", { d, fill: "none", stroke: color, "stroke-width": 2, opacity: 0.18, "stroke-linecap": "round" }, R.packets);
        const halo = el("circle", { r: 10, fill: color, opacity: 0.35, filter: "url(#fw-glow)" }, R.packets);
        const dot = el("circle", { r: 6, fill: color, stroke: "#fff", "stroke-width": 2 }, R.packets);
        const len = path.getTotalLength(), dur = Math.max(800, len / 0.3);
        return new Promise(resolve => {
          const t0 = performance.now();
          const frame = now => {
            const k = Math.min(1, (now - t0) / dur), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
            const p = path.getPointAtLength(e * len);
            [dot, halo].forEach(c => { c.setAttribute("cx", p.x); c.setAttribute("cy", p.y); });
            if (k < 1 && alive()) requestAnimationFrame(frame);
            else { path.remove(); dot.remove(); halo.remove(); resolve(); }
          };
          requestAnimationFrame(frame);
        });
      },
      async read(S_, eid, fid) {
        const e = engById(eid), f = fileById(fid);
        S.engs[eid].status = `reading ${f.name}…`; S.engs[eid].kind = null; S.storm.stages = [null, null, null]; A.render();
        await A.travel([[e.x - 20, Y.engBot], [e.x - 20, Y.bandMid], [f.x - 20, Y.bandMid], [f.x - 20, Y.fileTop + 8]], C.read);
        await A.travel([[f.x - 20, Y.fileTop + 8], [f.x - 20, Y.bandMid], [e.x - 20, Y.bandMid], [e.x - 20, Y.engBot]], C.read);
        const snap = S.engs[eid].snap, v = S.files[fid].v, cur = snap.find(s => s.f === fid);
        if (cur) { cur.v = v; cur.stale = false; } else snap.push({ f: fid, v });
        S.engs[eid].status = `read ${f.name} @ v${v}`;
        A.render();
      },
      async write(S_, eid, fid, opt = {}) {
        const e = engById(eid), f = fileById(fid);
        S.engs[eid].status = `writing ${f.name}…`; S.engs[eid].kind = null; A.render();
        await A.travel([[e.x + 20, Y.engBot], [e.x + 20, Y.bandMid]], C.write);
        // Validation stages light up in order.
        for (let i = 0; i < STAGES.length; i++) {
          const fail = opt.failStage === i;
          S.storm.stages = S.storm.stages.map((v, j) => (j < i ? "pass" : j === i ? (fail ? "fail" : "pass") : null));
          S.storm.msg = `${eid} → ${f.name}: checking ${STAGES[i].toLowerCase()}…`; S.storm.kind = null;
          A.render(); await A.pause(450);
          if (fail) break;
        }
        if (opt.failStage != null) {
          const st = fileById(opt.stale), seen = S.engs[eid].snap.find(s => s.f === opt.stale);
          seen.stale = true;
          S.storm.msg = `✗ ${eid} → ${f.name} rejected: ${st.name} read at v${seen.v}, now v${S.files[opt.stale].v} (${S.files[opt.stale].by})`;
          S.storm.kind = "bad"; S.locks[fid] = eid;
          S.engs[eid].status = `✗ rejected · stale ${st.name}`; S.engs[eid].kind = "bad";
          A.render();
          await A.travel([[e.x + 20, Y.bandMid], [e.x + 20, Y.engBot]], C.reject);
          await A.pause(900);
          return;
        }
        S.storm.msg = `✓ ${eid} → ${f.name}: snapshot current, write accepted`; S.storm.kind = "ok";
        A.render();
        await A.travel([[e.x + 20, Y.bandMid], [f.x + 20, Y.bandMid], [f.x + 20, Y.fileTop + 8]], C.write);
        S.files[fid].v += 1; S.files[fid].by = eid; delete S.locks[fid];
        const own = S.engs[eid].snap.find(s => s.f === fid);
        if (own) own.v = S.files[fid].v;
        S.engs[eid].status = `✓ wrote ${f.name} → v${S.files[fid].v}`; S.engs[eid].kind = "ok";
        A.render();
        if (!instant) { R.file[fid].box.classList.remove("flash"); void R.file[fid].box.getBBox(); R.file[fid].box.classList.add("flash"); }
        S.storm.stages = [null, null, null];
      },
    };
    return A;
  }

  // ---------- Player ----------
  function init() {
    const root = document.getElementById("framework");
    if (!root) return;
    const svg = root.querySelector("svg"), R = build(svg);
    const cap = root.querySelector(".fw-caption"), dots = root.querySelector(".fw-dots");
    const btnPlay = root.querySelector("[data-act=play]"), btnPrev = root.querySelector("[data-act=prev]"), btnNext = root.querySelector("[data-act=next]");
    const ctl = { token: 0, current: 0, step: 0, playing: false };
    let S = initialState();

    const dotBtns = STEPS.map((s, i) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "fw-dot"; b.innerHTML = `<span>${i + 1}</span>${s.title}`;
      b.addEventListener("click", () => { stop(); goTo(i); });
      dots.appendChild(b);
      return b;
    });

    function setCaption(i) {
      cap.innerHTML = `<div class="fw-step">Step ${i + 1} / ${STEPS.length}</div><div class="fw-title">${STEPS[i].title}</div><p>${STEPS[i].text}</p>`;
      dotBtns.forEach((b, j) => { b.classList.toggle("on", j === i); b.classList.toggle("done", j < i); });
      btnPrev.disabled = i === 0; btnNext.disabled = i === STEPS.length - 1;
    }

    // Jump straight to the end state of step i (no animation).
    async function goTo(i) {
      ctl.token++; R.packets.innerHTML = "";
      S = initialState();
      const A = makeAnim(R, S, ctl, true);
      for (let k = 0; k <= i; k++) await STEPS[k].run(S, A);
      ctl.step = i; render(R, S); setCaption(i);
    }

    async function animateStep(i) {
      ctl.current = ++ctl.token;
      const A = makeAnim(R, S, ctl, reduceMotion);
      setCaption(i);
      await STEPS[i].run(S, A);
      if (ctl.token !== ctl.current) return false;
      ctl.step = i; render(R, S);
      return true;
    }

    async function play() {
      if (ctl.playing) return;
      if (ctl.step >= STEPS.length - 1) await goTo(0);
      ctl.playing = true; btnPlay.textContent = "❚❚ Pause"; root.classList.add("playing");
      while (ctl.playing && ctl.step < STEPS.length - 1) {
        const ok = await animateStep(ctl.step + 1);
        if (!ok || !ctl.playing) break;
        // Linger long enough to read the caption (~4 words/s), within 2.5–4.5 s.
        const words = STEPS[ctl.step].text.replace(/<[^>]+>/g, "").split(/\s+/).length;
        await new Promise(r => setTimeout(r, Math.min(4500, Math.max(2500, words * 250))));
      }
      stop();
    }
    function stop() { ctl.playing = false; btnPlay.textContent = ctl.step >= STEPS.length - 1 ? "↻ Replay" : "▶ Play"; root.classList.remove("playing"); }

    btnPlay.addEventListener("click", () => (ctl.playing ? stop() : play()));
    btnNext.addEventListener("click", async () => { stop(); if (ctl.step < STEPS.length - 1) { await goTo(ctl.step); await animateStep(ctl.step + 1); stop(); } });
    btnPrev.addEventListener("click", () => { stop(); goTo(Math.max(0, ctl.step - 1)); });

    goTo(0);
    // Autoplay once when the diagram scrolls into view.
    if ("IntersectionObserver" in window && !reduceMotion) {
      const io = new IntersectionObserver(entries => {
        if (entries.some(en => en.isIntersecting)) { io.disconnect(); setTimeout(play, 400); }
      }, { threshold: 0.45 });
      io.observe(svg);
    }
    window.STORM_FRAMEWORK = { goTo, play, stop, state: () => S, steps: STEPS.length };
  }

  document.addEventListener("DOMContentLoaded", init);
})();
