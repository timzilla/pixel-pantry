// Pixel sprites drawn from character maps (one char per pixel, "." = transparent), rendered as crisp SVG rects.
// Elements with data-sprite="name" get the sprite; multi-frame sprites animate via CSS (.frames[data-n]).
(function () {
  const P = { k: "#2e1a0b", w: "#8b5a2b", W: "#c58a4f", d: "#5a3414", g: "#e8b84a", G: "#a3762a", r: "#c0392b", R: "#e8622a", y: "#f6c84a",
              s: "#9aa3a8", S: "#d8dde0", b: "#4a5a66", B: "#6f8291", o: "#f28c28", t: "#58a538", T: "#2f6b1f", p: "#f6e5b8", c: "#e9d2a3",
              f: "#e0ac6e", F: "#b8783f", n: "#3d2512", e: "#fff6dc", l: "#7ec8e3" };
  const pot = (flame, bubbles) => [
    "......................",
    "........" + bubbles[0] + "............",
    "......" + bubbles[1] + "..............",
    "......................",
    ".....kkkkkkkkkkkk.....",
    "....kssssssssssssk....",
    "...kSsssssssssssssk...",
    "..kbbbbbbbbbbbbbbbbk..",
    "kkkbBBBBBBBBBBBBBBbkkk",
    "k.kbBbbbbbbbbbbbbBbk.k",
    "k.kbbbbbbbbbbbbbbbbk.k",
    "kkkbbbbbbbbbbbbbbbbkkk",
    "...kbbbbbbbbbbbbbbk...",
    "....kbbbbbbbbbbbbk....",
    ".....kkkkkkkkkkkk.....",
    "......." + flame[0] + ".......",
    "......" + flame[1] + "......",
    ".....kkkkkkkkkkkkkk...",
    "....kWwwwwwwwwwwwwWk..",
    "....kwwwwwwwwwwwwwwk..",
    "....kkkkkkkkkkkkkkkk..",
    "......................"];
  const SPRITES = {
    hearth: [
      pot(["RyyoyyR", "RRoyyoRRRR"], ["..", ".."]),
      pot(["yoRRoyR", "RoyRRyoRRR"], ["S.", ".S"]),
      pot(["RRoyoRy", "RRRyooRRRy"], [".S", "S."]),
    ],
    pot: [pot(["RyyoyyR", "RRoyyoRRRR"], ["S.", ".S"])],
    cat: [[
      "....................",
      "..F..........F......",
      "..FF........FF......",
      "..FfF......FfF......",
      "..FffFFFFFFffF......",
      "..FffffffffffF......",
      "..FfnffffffnfF......",
      "..FffffffffffF......",
      "..FfffRfRffffFFFFF..",
      "...FffffffffffffffF.",
      "...FffffffffffffffF.",
      "...FFfffffffffffffF.",
      "....FFFFFFFFFFFFFFF.",
      "....................",
    ], [
      "....................",
      "..F..........F......",
      "..FF........FF......",
      "..FfF......FfF......",
      "..FffFFFFFFffF......",
      "..FffffffffffF......",
      "..FfnffffffnfF......",
      "..FffffffffffF......",
      "..FfffRfRffffFFFFF..",
      "...FffffffffffffffFF",
      "...FfffffffffffffffF",
      "...FFffffffffffffFF.",
      "....FFFFFFFFFFFFFF..",
      "....................",
    ]],
    basket: [[
      "......kkkkkkkk......",
      ".....kWwwwwwwwWk....",
      "....kw........wk....",
      "....kw........wk....",
      "kkkkkkkkkkkkkkkkkkkk",
      "kggggggggggggggggggk",
      "kGgGgGgGgGgGgGgGgGgk",
      "kgGgGgGgGgGgGgGgGgGk",
      "kGgGgGgGgGgGgGgGgGgk",
      "kgGgGgGgGgGgGgGgGgGk",
      ".kGgGgGgGgGgGgGgGgk.",
      ".kgGgGgGgGgGgGgGgGk.",
      "..kGgGgGgGgGgGgGgk..",
      "..kkkkkkkkkkkkkkkk..",
      "....................",
      "...................."]],
    glass: [[
      "kkkkkkkk",
      ".kgggggk",
      ".kgyyygk",
      "..kgygk.",
      "...kgk..",
      "..kg.gk.",
      ".kg...gk",
      ".kgyyygk",
      "kkkkkkkk"], [
      "kkkkkkkk",
      ".kgggggk",
      ".kg...gk",
      "..kg.gk.",
      "...kgk..",
      "..kgygk.",
      ".kgyyygk",
      ".kgyyygk",
      "kkkkkkkk"]],
  };
  function svg(map) {
    const h = map.length, w = Math.max(...map.map(r => r.length));
    let rects = "";
    map.forEach((row, y) => {
      let x = 0;
      while (x < w) {
        const ch = row[x] || ".";
        if (ch === "." || !P[ch]) { x++; continue; }
        let x2 = x + 1; while (x2 < w && (row[x2] || ".") === ch) x2++;  // run-length rows
        rects += `<rect x="${x}" y="${y}" width="${x2 - x}" height="1" fill="${P[ch]}"/>`; x = x2;
      }
    });
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges">${rects}</svg>`;
  }
  window.pixelSprite = function (name) {
    const frames = SPRITES[name]; if (!frames) return "";
    if (frames.length === 1) return svg(frames[0]);
    return `<div class="frames" data-n="${frames.length}">${frames.map(svg).join("")}</div>`;
  };
  document.querySelectorAll("[data-sprite]").forEach(el => { el.innerHTML = window.pixelSprite(el.dataset.sprite); });
})();
