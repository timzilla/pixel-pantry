"""Pixel Pantry: share a link, get a clean cook-mode page. See ../README.md."""
import contextlib, os, re, html as htmlmod, urllib.parse
from markupsafe import Markup, escape
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import extract, store, shopping
import weights
import buy
from parse_ingredient import parse

HERE = os.path.dirname(os.path.abspath(__file__))
@contextlib.asynccontextmanager
async def lifespan(app):
    try: n = store.reweigh(); print(f"pantry: re-weighed {n} recipe(s) against weights.json v{weights.TABLE['version']}")
    except Exception as e: print("pantry: reweigh failed", e)
    yield


app = FastAPI(title="Pixel Pantry", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
tpl = Jinja2Templates(directory=os.path.join(HERE, "templates"))
URL_RE = re.compile(r"https?://[^\s<>\"']+")


FRACTIONS = {0.5: (1, 2), 0.333: (1, 3), 0.667: (2, 3), 0.25: (1, 4), 0.75: (3, 4), 0.125: (1, 8), 0.375: (3, 8), 0.625: (5, 8), 0.875: (7, 8), 0.2: (1, 5)}


def split_qty(q):
    """(whole, numerator, denominator) for a quantity, or (None, None, None) when it is not a neat fraction."""
    whole, frac = int(q), q - int(q)
    for k, (n, d) in FRACTIONS.items():
        if abs(frac - k) < 0.02: return whole, n, d
    return None, None, None


def fmt_qty(q):
    """Quantity as HTML: fractions are stacked real digits (Pixelify's single ½ glyph reads as ⅛)."""
    if q is None: return ""
    whole, n, d = split_qty(q)
    if n: return Markup((str(whole) if whole else "") + f'<span class="frac"><sup>{n}</sup>\u2044<sub>{d}</sub></span>')
    return Markup(escape(f"{q:g}"))


def text_qty(q):
    """Quantity as plain text for paper and APIs: 1 1/4, 3/4, 2."""
    if q is None: return ""
    whole, n, d = split_qty(q)
    if n: return (f"{whole} " if whole else "") + f"{n}/{d}"
    return f"{q:g}"


def minutes(v):
    if not v: return ""
    try: v = int(v)
    except (TypeError, ValueError): return str(v)
    h, m = divmod(v, 60)
    return (f"{h} h " if h else "") + (f"{m} min" if m else "") or "0 min"


tpl.env.filters["qty"] = fmt_qty
tpl.env.globals["basket_count"] = shopping.count
tpl.env.filters["minutes"] = minutes
TIMER_RE = re.compile(r"(\d+(?:\s*(?:-|–|to)\s*\d+)?)\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b", re.I)


def step_html(step: str) -> str:
    """Escape a step and turn 'for 10 minutes' into a timer button."""
    out, pos = [], 0
    for m in TIMER_RE.finditer(step):
        out.append(htmlmod.escape(step[pos:m.start()]))
        n = re.findall(r"\d+", m.group(1)); unit = m.group(2).lower()
        secs = int(n[-1]) * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1)
        out.append(f'<button class="timer" data-seconds="{secs}" type="button">{htmlmod.escape(m.group(0))}</button>')
        pos = m.end()
    out.append(htmlmod.escape(step[pos:]))
    return "".join(out)


tpl.env.filters["step_html"] = step_html


@app.get("/", response_class=HTMLResponse)
def shelf(request: Request, q: str = "", err: str = "", app: str = ""):
    recipes = store.all_recipes()
    if q:
        ql = q.lower()
        recipes = [r for r in recipes if ql in r["title"].lower() or any(ql in i["name"].lower() for i in r.get("ingredients", []))]
    app_link = ""
    if app:  # Android intent link: opens Pixel Pantry with the url, which reads the page on the phone
        app_link = "intent://add?url=" + urllib.parse.quote(app, safe="") + "#Intent;scheme=kitchen;package=io.github.timzilla.pixelpantry;end"
    return tpl.TemplateResponse(request, "shelf.html", {"recipes": recipes, "q": q, "err": err, "app_link": app_link})


def _add(url_text: str):
    m = URL_RE.search(url_text or "")
    if not m:
        return RedirectResponse("/?err=" + urllib.parse.quote("That didn't look like a link."), status_code=303)
    url = m.group(0).rstrip(").,")
    for r in store.all_recipes():
        if r.get("source") == url:
            return RedirectResponse(f"/r/{r['slug']}", status_code=303)
    try:
        recipe = extract.extract(url)
    except Exception as e:
        print(f"extract failed for {url}: {e!r}")
        msg = f"Couldn't fetch that one: {str(e).splitlines()[0][:140]}"
        if "403" in str(e) or "401" in str(e):
            msg = f"{httpx.URL(url).host} only talks to real browsers, so the shelf can't read it from here."
            return RedirectResponse("/?err=" + urllib.parse.quote(msg) + "&app=" + urllib.parse.quote(url), status_code=303)
        return RedirectResponse("/?err=" + urllib.parse.quote(msg), status_code=303)
    slug = store.save(recipe)
    return RedirectResponse(f"/r/{slug}", status_code=303)


@app.get("/add")
def add_get(url: str = ""):
    return _add(url)


@app.post("/add")
def add_post(url: str = Form("")):
    return _add(url)


@app.post("/add-html")
async def add_html(request: Request):
    """The phone's browser posts a page it has already loaded (bookmarklet), for sites that refuse server fetches."""
    form = await request.form(max_part_size=24 * 1024 * 1024)
    url, html = (form.get("url") or "").strip(), form.get("html") or ""
    if not url or len(html) < 500:
        return RedirectResponse("/?err=" + urllib.parse.quote("The page didn't come through. Try the bookmark again once the page has fully loaded."), status_code=303)
    for r in store.all_recipes():
        if r.get("source") == url:
            return RedirectResponse(f"/r/{r['slug']}", status_code=303)
    try:
        recipe = extract.extract(url, html=html)
    except Exception as e:
        print(f"extract (html) failed for {url}: {e!r}")
        return RedirectResponse("/?err=" + urllib.parse.quote(f"Got the page, but couldn't find a recipe in it: {str(e)[:140]}"), status_code=303)
    return RedirectResponse(f"/r/{store.save(recipe)}", status_code=303)


@app.get("/add-html-app", response_class=HTMLResponse)
def add_html_app():
    """Loaded by the Android app after it grabbed a page: posts the page from the app's bridge to /add-html."""
    return HTMLResponse("""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Pixel Pantry</title>
<body style="background:#f6e5b8;font-family:sans-serif;padding:24px;color:#3d2512"><p id="m">Sending the page to the shelf…</p>
<form id="f" method="post" action="/add-html" style="display:none"><input name="url" id="u"><textarea name="html" id="h"></textarea></form>
<script>try{if(window.Kitchen&&Kitchen.html().length>500){document.getElementById('u').value=Kitchen.url();document.getElementById('h').value=Kitchen.html();document.getElementById('f').submit();}else{document.getElementById('m').textContent='Nothing to send. Share a recipe page to Pixel Pantry first.';}}catch(e){document.getElementById('m').textContent='Could not hand the page over: '+e;}</script>""")


APK_VERSION_FILE = "/apk/version.txt"


def apk_version():
    try: return open(APK_VERSION_FILE).read().strip()
    except Exception: return "0"


tpl.env.globals["apk_version"] = apk_version


@app.get("/kitchen.apk")
@app.get("/kitchen-{ver}.apk")
def apk(ver: str = ""):
    p = "/apk/kitchen.apk" if os.path.exists("/apk/kitchen.apk") else os.path.join(os.path.dirname(HERE), "android", "out", "kitchen.apk")
    return FileResponse(p, media_type="application/vnd.android.package-archive", filename=f"kitchen-{apk_version()}.apk", headers={"Cache-Control": "no-store"}) if os.path.exists(p) else PlainTextResponse("The app has not been built yet.", status_code=404)


@app.post("/app-log")
def app_log(msg: str = Form("")):
    print(f"[phone app] {msg[:600]}")
    return JSONResponse({"ok": True})


@app.post("/share")
def share(url: str = Form(""), text: str = Form(""), title: str = Form("")):
    """Android share target (manifest.webmanifest). The link usually arrives in `text`."""
    return _add(" ".join([url, text, title]))


@app.get("/r/{slug}.json")
def recipe_json(slug: str):
    r = store.load(slug)
    return JSONResponse(r or {"error": "no such recipe"}, status_code=200 if r else 404)


@app.get("/r/{slug}", response_class=HTMLResponse)
def recipe(request: Request, slug: str):
    r = store.load(slug)
    if not r:
        return RedirectResponse("/?err=No+such+recipe", status_code=303)
    return tpl.TemplateResponse(request, "recipe.html", {"r": r})


@app.post("/r/{slug}/reweigh")
def recipe_reweigh(slug: str):
    """Recompute grams for one recipe from the weight table and ask Claude about anything left (when a key is set)."""
    if not store.load(slug): raise HTTPException(404)
    store.reweigh(slug, ask_claude=True)
    return RedirectResponse(f"/r/{slug}", status_code=303)


@app.post("/r/{slug}/delete")
def recipe_delete(slug: str):
    store.delete(slug)
    return RedirectResponse("/", status_code=303)


CHAR = os.environ.get("CHAR_URL", "").rstrip("/")   # optional: a Char print service (https://github.com/timzilla/pixel-pantry#printing); empty hides the button
CHAR_HEADERS = {"Authorization": "Bearer " + os.environ["CHAR_TOKEN"]} if os.environ.get("CHAR_TOKEN") else {}   # when Char is locked with CHAR_TOKEN
tpl.env.globals["char"] = bool(CHAR)


@app.post("/r/{slug}/print")
def recipe_print(slug: str, servings: str = Form(""), steps: str = Form("on")):
    """Hand the recipe to Char, which lays out the slip (its `recipe` module) and queues it for the kitchen printer."""
    if not CHAR: return JSONResponse({"error": "No printer configured"}, status_code=404)
    try:
        r = httpx.post(CHAR + "/api/print", json={"module": "recipe", "params": {"slug": slug, "servings": servings, "steps": steps, "grams": "on"}, "source": "kitchen"}, headers=CHAR_HEADERS, timeout=15)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": f"Char is not answering ({e.__class__.__name__})"}, status_code=502)


@app.get("/api/recipes")
def api_recipes():
    return [{"slug": r["slug"], "title": r["title"]} for r in store.all_recipes()]


@app.get("/images/{name}")
def image(name: str):
    p = os.path.join(store.IMAGES, os.path.basename(name))
    return FileResponse(p) if os.path.exists(p) else PlainTextResponse("", status_code=404)


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(os.path.join(HERE, "static", "manifest.webmanifest"), media_type="application/manifest+json")


@app.get("/sw.js")
def sw():
    return FileResponse(os.path.join(HERE, "static", "sw.js"), media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})


@app.get("/health")
def health():
    return {"ok": True, "recipes": len(store.all_recipes()), "claude": bool(os.environ.get("ANTHROPIC_API_KEY"))}


# ---- shopping list -------------------------------------------------------------------------------------------------
@app.get("/list", response_class=HTMLResponse)
def shopping_list(request: Request):
    items = shopping.items()
    for it in items: it["buy"] = buy.suggest(it["name"], it.get("grams"), it.get("qty"), it.get("unit"))
    groups = []
    for it in items:
        if it["done"]: continue
        if not groups or groups[-1][0] != it["aisle"]: groups.append((it["aisle"], []))
        groups[-1][1].append(it)
    done = [i for i in items if i["done"]]
    return tpl.TemplateResponse(request, "list.html", {"groups": groups, "done": done, "total": len(items) - len(done)})


@app.post("/list/add")
async def list_add(request: Request):
    """From a recipe page: form fields slug, scale (servings factor) and idx (one per chosen ingredient)."""
    form = await request.form()
    r = store.load(form.get("slug", ""))
    if not r: return RedirectResponse("/list", status_code=303)
    try: k = float(form.get("scale") or 1)
    except ValueError: k = 1.0
    for idx in form.getlist("idx"):
        try: i = r["ingredients"][int(idx)]
        except (ValueError, IndexError): continue
        qty = round(i["qty"] * k, 2) if i.get("qty") is not None else None
        grams = round(i["grams"] * k) if i.get("grams") is not None else None
        shopping.add(i["name"], qty, i.get("unit"), grams, r["title"])
    return RedirectResponse("/list", status_code=303)


@app.post("/list/quick")
def list_quick(text: str = Form("")):
    for line in re.split(r"[\n,;]+", text):
        if line.strip():
            i = parse(line.strip()); shopping.add(i["name"], i["qty"], i["unit"], i["grams"])
    return RedirectResponse("/list", status_code=303)


@app.post("/list/item")
def list_item(id: str = Form(...), done: str = Form("1")):
    shopping.set_done(id, done == "1")
    return JSONResponse({"ok": True, "left": shopping.count()})


@app.post("/list/remove")
def list_remove(id: str = Form(...)):
    shopping.remove(id)
    return RedirectResponse("/list", status_code=303)


def shopping_markdown():
    """The basket as the printed checklist: what to buy, grouped by aisle."""
    todo = [i for i in shopping.items() if not i["done"]]
    if not todo: return None, 0
    lines, aisle = ["# Shopping"], None
    for i in todo:
        if i["aisle"] != aisle: aisle = i["aisle"]; lines.append(f"## {aisle}")
        amt = (f"{text_qty(i['qty'])} {i.get('unit') or ''}".strip() + " ") if i.get("qty") is not None else ""
        g = f" ({i['grams']} g)" if i.get("grams") else ""
        b = buy.suggest(i["name"], i.get("grams"), i.get("qty"), i.get("unit"))
        if b and b.get("check"): lines.append(f"- [ ] {i['name']}: check the cupboard ({b['note'].split('; ')[-1]})")
        elif b and b.get("named") and not b.get("same"): lines.append(f"- [ ] {b['buy']} (for {amt}{i['name']})")      # "2 lemons (for 1/4 cup lemon juice)"
        elif b and b.get("note") != "as the recipe says": lines.append(f"- [ ] {i['name']}: {b['buy']}")   # "flour: 1 × 2 lb bag"
        else: lines.append(f"- [ ] {amt}{i['name']}{g}")
    lines += ["", f"{len(todo)} to get"]
    return "\n".join(lines), len(todo)


@app.post("/list/print")
def list_print():
    """The basket as a checklist strip, grouped by aisle, via Char (markdown document)."""
    if not CHAR: return JSONResponse({"error": "No printer configured"}, status_code=404)
    md, n = shopping_markdown()
    if not md: return JSONResponse({"error": "The basket is empty"}, status_code=400)
    try:
        r = httpx.post(CHAR + "/api/print", json={"markdown": md, "title": "Shopping list", "source": "kitchen"}, headers=CHAR_HEADERS, timeout=15)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": f"Char is not answering ({e.__class__.__name__})"}, status_code=502)


@app.post("/list/clear")
def list_clear(all: str = Form("")):
    shopping.clear(done_only=not all)
    return RedirectResponse("/list", status_code=303)
