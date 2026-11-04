"""Recipes as Markdown files with YAML front matter in $RECIPES_DATA/recipes/<slug>.md; hero images in images/."""
import os, re, datetime as dt, yaml

DATA = os.environ.get("RECIPES_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
RECIPES, IMAGES = os.path.join(DATA, "recipes"), os.path.join(DATA, "images")
os.makedirs(RECIPES, exist_ok=True); os.makedirs(IMAGES, exist_ok=True)


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:70] or "recipe"


def unique_slug(title: str) -> str:
    base = slugify(title); slug, n = base, 2
    while os.path.exists(os.path.join(RECIPES, slug + ".md")):
        slug = f"{base}-{n}"; n += 1
    return slug


def save(recipe: dict) -> str:
    slug = recipe.get("slug") or unique_slug(recipe["title"])
    recipe["slug"] = slug
    recipe.setdefault("added", dt.datetime.now().isoformat(timespec="seconds"))
    body = recipe.pop("notes", "") or ""
    front = yaml.safe_dump(recipe, allow_unicode=True, sort_keys=False, width=1000)
    with open(os.path.join(RECIPES, slug + ".md"), "w") as f:
        f.write(f"---\n{front}---\n\n{body}\n")
    return slug


def load(slug: str):
    p = os.path.join(RECIPES, slug + ".md")
    if not os.path.exists(p): return None
    raw = open(p).read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
    if not m: return None
    r = yaml.safe_load(m.group(1)) or {}
    r["notes"] = m.group(2).strip(); r["slug"] = slug
    return r


def all_recipes():
    out = []
    for fn in os.listdir(RECIPES):
        if fn.endswith(".md"):
            r = load(fn[:-3])
            if r: out.append(r)
    return sorted(out, key=lambda r: r.get("added", ""), reverse=True)


def delete(slug: str):
    for p in (os.path.join(RECIPES, slug + ".md"), os.path.join(IMAGES, slug + ".jpg")):
        if os.path.exists(p): os.remove(p)


def reweigh(slug=None, ask_claude=False):
    """Recompute grams from the current weight table for one recipe or all of them; optionally ask Claude for the rest.
    Runs at startup (table only) so a better table improves every recipe already on the shelf."""
    import weights
    n = 0
    for r in ([load(slug)] if slug else all_recipes()):
        if not r: continue
        r = load(r["slug"]) if "ingredients" not in r else r
        changed = weights.reweigh(r["ingredients"])
        if ask_claude: changed = weights.fill_missing(r["ingredients"]) or changed
        if changed: save(r); n += 1
    return n
