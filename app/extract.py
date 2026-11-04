"""Fetch a page and pull the recipe out: schema.org data first (recipe-scrapers), Claude as the fallback."""
import os, re, httpx
from recipe_scrapers import scrape_html
import claude_fallback, store
from parse_ingredient import parse
import weights

UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Mobile Safari/537.36"


def fetch(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=25, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"}) as c:
        r = c.get(url); r.raise_for_status()
        return r.text


def _call(fn, default=None):
    try:
        v = fn()
        return v if v not in ("", [], None) else default
    except Exception:
        return default


def from_schema(url: str, html: str):
    try:
        s = scrape_html(html, org_url=url, supported_only=False)
    except Exception:
        return None
    ingredients = _call(s.ingredients, [])
    steps = _call(s.instructions_list, [])
    if not ingredients or not steps:
        return None
    return {"title": _call(s.title, "Untitled"), "ingredients": ingredients, "steps": steps, "yields": _call(s.yields),
            "prep": _call(s.prep_time), "cook": _call(s.cook_time), "total": _call(s.total_time),
            "description": _call(s.description), "image": _call(s.image), "how": "schema.org"}


def cache_image(slug: str, image_url: str):
    if not image_url: return None
    try:
        with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": UA}) as c:
            r = c.get(image_url); r.raise_for_status()
            if not r.headers.get("content-type", "").startswith("image/"): return None
            open(os.path.join(store.IMAGES, slug + ".jpg"), "wb").write(r.content)
        return f"/images/{slug}.jpg"
    except Exception:
        return None


def extract(url: str, html: str = None) -> dict:
    html = html if html is not None else fetch(url)
    rec = from_schema(url, html)
    if rec is None:
        if not claude_fallback.available():
            raise ValueError("This page has no recipe data I can read, and the Claude fallback is not configured yet.")
        rec = claude_fallback.extract(url, html)
    servings = None
    if rec.get("yields"):
        m = re.search(r"(\d+)", str(rec["yields"]))
        servings = int(m.group(1)) if m else None
    recipe = {
        "title": str(rec["title"]).strip(), "source": url, "site": re.sub(r"^www\.", "", httpx.URL(url).host or ""),
        "yields": rec.get("yields"), "servings": servings, "prep": rec.get("prep"), "cook": rec.get("cook"), "total": rec.get("total"),
        "description": (rec.get("description") or "").strip()[:400], "how": rec["how"],
        "ingredients": [parse(str(i)) for i in rec["ingredients"] if str(i).strip()],
        "steps": [re.sub(r"\s+", " ", str(st)).strip() for st in rec["steps"] if str(st).strip()],
    }
    weights.fill_missing(recipe["ingredients"])
    slug = store.unique_slug(recipe["title"])
    recipe["slug"] = slug
    recipe["image"] = cache_image(slug, rec.get("image"))
    return recipe
