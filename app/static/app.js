// Pixel Pantry page behaviour: tabs, ingredient checklist + scaling, one-step-at-a-time method, timers, wake lock, SW.
(function () {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  // basket page: ticking an item moves it to "in the bag" without a reload storm
  $$(".bitem .donebox").forEach(cb => cb.onchange = () => {
    const li = cb.closest(".bitem"); li.classList.toggle("isdone", cb.checked);
    fetch("/list/item", { method: "POST", body: new URLSearchParams({ id: li.dataset.id, done: cb.checked ? "1" : "0" }) }).then(() => setTimeout(() => location.reload(), 350));
  });
  // print (recipe strip or shopping list): Char lays out the slip. Without a printer the button explains itself.
  const pb = $("#printbtn"), ph = $("#printhelp");
  if (pb) pb.onclick = async () => {
    if (ph) { ph.classList.toggle("hidden"); return; }
    const art = $("article.recipe");
    pb.disabled = true; const was = pb.textContent; pb.textContent = "Sending…";
    try {
      let r;
      if (art) {
        const sv = ($("#servings") && $("#servings").value) || art.dataset.servings || "";
        r = await fetch(`/r/${art.dataset.slug}/print`, { method: "POST", body: new URLSearchParams({ servings: sv, steps: "on" }) });
      } else r = await fetch("/list/print", { method: "POST" });
      const j = await r.json(); pb.textContent = j.job ? "Printing ✓" : (j.error || "Printer error");
    } catch { pb.textContent = "Printer error"; }
    setTimeout(() => { pb.textContent = was; pb.disabled = false; }, 4000);
  };
  const art = $("article.recipe"); if (!art) return;
  // add-to-basket picker
  const picker = $("#picker");
  $("#tobasket").onclick = () => { picker.classList.toggle("hidden"); if (!picker.classList.contains("hidden")) picker.scrollIntoView({ behavior: "smooth", block: "start" }); };
  $("#pickcancel").onclick = () => picker.classList.add("hidden");
  const slug = art.dataset.slug, store = key => `kitchen:${slug}:${key}`;
  const get = (k, d) => { try { const v = localStorage.getItem(store(k)); return v === null ? d : JSON.parse(v); } catch { return d; } };
  const set = (k, v) => { try { localStorage.setItem(store(k), JSON.stringify(v)); } catch {} };

  // tabs
  $$(".tab").forEach(t => t.onclick = () => { $$(".tab").forEach(x => x.classList.toggle("on", x === t)); $$(".tabpane").forEach(p => p.classList.toggle("hidden", p.id !== "pane-" + t.dataset.tab)); set("tab", t.dataset.tab); });
  const tab = get("tab", "ingredients"); const tb = $(`.tab[data-tab="${tab}"]`); if (tb) tb.click();

  // checklist, remembered per recipe
  const checked = new Set(get("checked", []));
  $$(".ing").forEach((li, i) => { const cb = $("input", li); cb.checked = checked.has(i); cb.onchange = () => { cb.checked ? checked.add(i) : checked.delete(i); set("checked", [...checked]); }; });

  // servings scaling: multiplies quantities and grams; original always available by returning to the base number
  const base = parseInt(art.dataset.servings) || 0; let servings = get("servings", base) || base;
  // returns HTML: fractions are stacked real digits, matching fmt_qty() on the server
  const fmt = q => { const whole = Math.floor(q), f = q - whole, fr = { 0.5: [1, 2], 0.333: [1, 3], 0.667: [2, 3], 0.25: [1, 4], 0.75: [3, 4], 0.125: [1, 8], 0.375: [3, 8], 0.625: [5, 8], 0.875: [7, 8], 0.2: [1, 5] };
    for (const k in fr) if (Math.abs(f - k) < 0.03) return (whole || "") + `<span class="frac"><sup>${fr[k][0]}</sup>\u2044<sub>${fr[k][1]}</sub></span>`;
    return q >= 10 ? String(Math.round(q)) : String(Math.round(q * 100) / 100); };
  const rescale = () => {
    const k = base ? servings / base : 1; $("#servings").textContent = base ? servings : "?"; $("#pickscale").value = k;
    $$(".ing").forEach(li => { const q = parseFloat(li.dataset.qty), qm = parseFloat(li.dataset.qtymax), g = parseFloat(li.dataset.grams);
      const qe = $(".q", li), ge = $(".g", li);
      if (qe && !isNaN(q)) qe.innerHTML = fmt(q * k) + (!isNaN(qm) ? "–" + fmt(qm * k) : "");
      if (ge && !isNaN(g)) ge.textContent = Math.round(g * k); });
  };
  $$("[data-scale]").forEach(b => b.onclick = () => { if (!base) return; servings = Math.max(1, servings + parseInt(b.dataset.scale)); set("servings", servings); rescale(); });
  rescale();
  const sg = $("#showgrams"); sg.checked = get("grams", true); document.body.classList.toggle("nograms", !sg.checked);
  sg.onchange = () => { set("grams", sg.checked); document.body.classList.toggle("nograms", !sg.checked); };

  // method: one step at a time, swipe or arrows
  const steps = $$(".step"); let cur = Math.min(get("step", 0), steps.length - 1);
  const show = i => { cur = Math.max(0, Math.min(steps.length - 1, i)); steps.forEach((s, j) => s.classList.toggle("on", j === cur)); $("#stepnum").textContent = cur + 1; set("step", cur); };
  $("#prev").onclick = () => show(cur - 1); $("#next").onclick = () => show(cur + 1); show(cur);
  const all = $("#allsteps"), setAll = on => { $(".steps").classList.toggle("all", on); $(".stepnav").classList.toggle("all", on); };
  all.checked = get("all", false); setAll(all.checked);
  all.onchange = () => { set("all", all.checked); setAll(all.checked); };
  let sx = null; const pane = $("#pane-method");
  pane.addEventListener("touchstart", e => { sx = e.touches[0].clientX; }, { passive: true });
  pane.addEventListener("touchend", e => { if (sx === null) return; const dx = e.changedTouches[0].clientX - sx; sx = null; if (Math.abs(dx) > 60) show(cur + (dx < 0 ? 1 : -1)); });
  document.addEventListener("keydown", e => { if (/INPUT|TEXTAREA/.test(e.target.tagName)) return; if (e.key === "ArrowRight") show(cur + 1); if (e.key === "ArrowLeft") show(cur - 1); });

  // timers: tap "10 minutes" in a step; an hourglass counts down bottom-right and chimes
  let audio;
  const chime = () => { try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); const t = audio.currentTime;
    [[659, 0], [784, .15], [1047, .3], [784, .5], [1047, .65], [1319, .8]].forEach(([f, d]) => { const o = audio.createOscillator(), g = audio.createGain(); o.type = "square"; o.frequency.value = f; g.gain.setValueAtTime(.08, t + d); g.gain.exponentialRampToValueAtTime(.001, t + d + .14); o.connect(g).connect(audio.destination); o.start(t + d); o.stop(t + d + .15); }); } catch {} };
  const timers = $("#timers");
  $$(".timer").forEach(b => b.onclick = () => {
    let left = parseInt(b.dataset.seconds); const el = document.createElement("div"); el.className = "tmr";
    el.innerHTML = `<span class="glass">${window.pixelSprite("glass")}</span><span class="t"></span><span class="x" title="dismiss">✕</span>`;
    timers.appendChild(el); const txt = $(".t", el);
    const draw = () => { const m = Math.floor(left / 60), s = left % 60; txt.textContent = `${m}:${String(s).padStart(2, "0")}`; };
    draw(); if (audio && audio.state === "suspended") audio.resume();
    const iv = setInterval(() => { left--; draw(); if (left <= 0) { clearInterval(iv); el.classList.add("done"); txt.textContent = "Done!"; chime(); setTimeout(chime, 2500); if (navigator.vibrate) navigator.vibrate([300, 150, 300]); } }, 1000);
    $(".x", el).onclick = () => { clearInterval(iv); el.remove(); };
  });

  // keep the screen on while cooking
  let lock = null; const wb = $("#wake");
  wb.onclick = async () => { try { if (lock) { await lock.release(); lock = null; } else { lock = await navigator.wakeLock.request("screen"); lock.addEventListener("release", () => { lock = null; wb.textContent = "Keep screen on"; }); } wb.textContent = lock ? "Screen stays on ✓" : "Keep screen on"; } catch { wb.textContent = "Not supported here"; } };
  if (!("wakeLock" in navigator)) wb.disabled = true;
})();
