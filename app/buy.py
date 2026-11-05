"""What to actually buy for a basket line: "2 lemons", "1 head of garlic", "1 x 5 lb bag".

Recipes ask for amounts; stores sell things. For each basket item with a weight this picks the most useful answer:
  1. Derived ingredients go back to the thing you buy: lemon juice -> lemons, minced garlic -> heads, zest -> fruit.
  2. Things sold loose or by count (produce, eggs, chicken breasts) -> how many, rounded up.
  3. Herbs and greens sold by the bunch -> bunches.
  4. Everything else -> the package sizes US stores stock (packs.json: USDA Branded Foods plus hand-picked staples),
     choosing the smallest common package that covers the amount, or several of the largest.
Each answer says roughly how much is left over. Spices are never converted (a jar lasts for years).
"""
import json, math, os, re
import weights

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(HERE, "packs.json"), encoding="utf-8") as f: PACKS = json.load(f)["packs"]
except OSError:
    PACKS = {}

# derived ingredient (weights.json first phrase) -> (what you buy, grams of the derived thing per item, singular, plural)
DERIVED = {
    "lemon juice": ("lemon", 45, "lemon", "lemons"), "lime juice": ("lime", 30, "lime", "limes"), "lemon zest": ("lemon", 6, "lemon", "lemons"),
    "lime zest": ("lime", 4, "lime", "limes"), "minced garlic": ("garlic", 40, "head of garlic", "heads of garlic"),
    "garlic cloves": ("garlic", 40, "head of garlic", "heads of garlic"), "ginger": ("ginger", 60, "knob of ginger (about 3 inches)", "knobs of ginger"),
    "cooked chicken": ("chicken", 500, "rotisserie chicken (about 3½ cups of meat)", "rotisserie chickens"),
}
# sold by count: weights.json first phrase -> (singular, plural); grams come from the entry's `each`
COUNTED = {
    "onion": ("onion", "onions"), "green onions": ("bunch of green onions (about 7)", "bunches of green onions"), "shallots": ("shallot", "shallots"),
    "leeks": ("leek", "leeks"), "tomato": ("tomato", "tomatoes"), "roma tomatoes": ("roma tomato", "roma tomatoes"), "potatoes": ("potato", "potatoes"),
    "sweet potatoes": ("sweet potato", "sweet potatoes"), "carrots": ("carrot", "carrots"), "celery": ("head of celery", "heads of celery"),
    "bell pepper": ("bell pepper", "bell peppers"), "jalapeno": ("jalapeño", "jalapeños"), "poblano": ("poblano", "poblanos"), "cucumber": ("cucumber", "cucumbers"),
    "zucchini": ("zucchini", "zucchini"), "eggplant": ("eggplant", "eggplants"), "avocado": ("avocado", "avocados"), "lemon": ("lemon", "lemons"),
    "lime": ("lime", "limes"), "orange": ("orange", "oranges"), "apple": ("apple", "apples"), "banana": ("banana", "bananas"), "pear": ("pear", "pears"),
    "peach": ("peach", "peaches"), "mango": ("mango", "mangoes"), "garlic": ("head of garlic", "heads of garlic"), "broccoli": ("head of broccoli", "heads of broccoli"),
    "cauliflower": ("head of cauliflower", "heads of cauliflower"), "cabbage": ("head of cabbage", "heads of cabbage"), "romaine": ("head of romaine", "heads of romaine"),
    "iceberg": ("head of lettuce", "heads of lettuce"), "corn": ("ear of corn", "ears of corn"), "chicken breasts": ("chicken breast", "chicken breasts"),
    "chicken thighs": ("chicken thigh", "chicken thighs"), "pork chops": ("pork chop", "pork chops"), "salmon": ("salmon fillet", "salmon fillets"),
}
# grams per countable item when the entry's `each` means something else (celery entry's `each` is one stalk)
COUNT_GRAMS = {"celery": 500, "garlic": 40, "green onions": 100, "broccoli": 600}
BUNCHED = {"cilantro", "parsley", "basil", "mint", "dill", "chives", "kale", "swiss chard", "fresh thyme", "fresh rosemary", "fresh sage", "fresh oregano", "asparagus"}


def _key(entry): return entry["m"][0]


def _n(qty, one, many): return f"{qty} {one if qty == 1 else many}"


def _left(g, entry=None):
    if g < 15: return ""
    cup = (entry or {}).get("cup")
    if entry and entry.get("dens") and cup:   # liquids read better in cups
        c = g / cup
        return "about " + (f"{c:.1f}".rstrip("0").rstrip(".") if c < 4 else f"{c:.0f}") + (" cup" if round(c, 1) == 1 else " cups") + " left"
    return f"about {g:,.0f} g left" if g < 1000 else f"about {g / 1000:.1f} kg left"


def _packs_for(entry):
    return (PACKS.get(_key(entry)) or {}).get("packs") or []


# shelf-stable things most kitchens already have open: a small amount says "check the cupboard" instead of "buy a box"
STAPLES = {"all-purpose flour", "bread flour", "granulated sugar", "brown sugar", "powdered sugar", "salt", "kosher salt", "baking powder", "baking soda", "cornstarch",
           "vanilla extract", "olive oil", "vegetable oil", "sesame oil", "vinegar", "balsamic vinegar", "soy sauce", "fish sauce", "worcestershire sauce", "hot sauce", "honey",
           "maple syrup", "molasses", "cocoa powder", "active dry yeast", "ketchup", "mustard", "mayonnaise", "white rice", "rolled oats", "peanut butter", "butter", "breadcrumbs",
           "panko", "chicken broth", "tomato paste", "cooking spray", "sriracha", "bbq sauce"}


def _smallest(entry):
    packs = _packs_for(entry)
    if not packs: return None
    dens = entry.get("dens") or ((entry.get("cup") / 236.6) if entry.get("cup") else 1.0)
    return min(p["g"] * (dens if p["kind"] == "ml" else 1) for p in packs)


def _pack_choice(need_g, entry):
    """need_g is grams; for packs sold by volume compare in ml using the entry's density."""
    packs = _packs_for(entry)
    if not packs: return None
    dens = entry.get("dens") or ((entry.get("cup") / 236.6) if entry.get("cup") else 1.0)
    def amount(p): return p["g"] * (dens if p["kind"] == "ml" else 1)   # pack contents in grams
    common = [p for p in packs if p.get("share", 0) >= 0.12] or packs
    for pool in (common, packs):
        fit = sorted((p for p in pool if amount(p) >= need_g), key=amount)
        if fit:
            p = fit[0]; return f"1 × {p['label']}", amount(p) - need_g
    big = max(packs, key=amount); n = math.ceil(need_g / amount(big))
    return f"{n} × {big['label']}", n * amount(big) - need_g


CONTAINERS = {"can", "tin", "jar", "bottle", "carton", "package", "pack", "bag", "box", "container", "tub", "pouch", "tube", "block", "packet", "envelope", "stick", "head", "bunch"}


def suggest(name, grams, qty=None, unit=None):
    """{'buy': '2 lemons', 'note': 'about 15 g left'} or None when there is nothing useful to say."""
    if re.match(r"\s*(leftover|left-over|day-old)\b", name, re.I): return None   # already in the fridge
    e, phrase = weights.match(name)
    if not e or e.get("spice"): return None
    k = _key(e)
    if unit in CONTAINERS and qty:   # the recipe already says what to buy: "1 (14.5 oz) can", "2 sticks"
        n = math.ceil(qty); size = f" ({grams / n / 28.35:.1f} oz)".replace(".0 oz", " oz") if grams and unit not in ("head", "bunch", "stick") else ""
        return {"buy": f"{n} {unit if n == 1 else unit + ('es' if unit.endswith(('x', 'ch', 'sh')) else 's')}{size}", "note": "as the recipe says"}
    if not grams or grams <= 0:      # no amount ("fresh cilantro"): one of whatever it is sold as
        if k in BUNCHED: return {"buy": "1 bunch", "note": "no amount given"}
        if k in COUNTED: return {"buy": "1 " + COUNTED[k][0], "note": "no amount given", "named": True}
        return None
    if k in DERIVED:
        _, per, one, many = DERIVED[k]; n = max(1, math.ceil(grams / per - 0.15))
        return {"buy": _n(n, one, many), "note": f"about {per} g per {one.split(' (')[0]}", "named": True}
    if k == "eggs":
        n = math.ceil(grams / 50 - 0.1)
        return {"buy": "1 dozen" if n <= 12 else "18-pack" if n <= 18 else f"{math.ceil(n / 12)} dozen", "note": f"{n} egg{'s' if n != 1 else ''} needed"}
    if k in COUNTED:
        each = COUNT_GRAMS.get(k) or e.get("each")
        if each:
            one, many = COUNTED[k]
            n = math.ceil(qty) if (qty and not unit and k not in COUNT_GRAMS) else max(1, math.ceil(grams / each - 0.15))   # "2 large onions" buys 2
            same = bool(qty) and not unit and n == math.ceil(qty)   # "2 avocados" already says what to buy
            if unit in ("lb", "oz", "g", "kg"):                       # bought by weight: the count is just a guide
                return {"buy": f"about {_n(n, one, many)}", "note": f"sold by weight; about {each:g} g each", "named": True}
            return {"buy": _n(n, one, many), "note": f"about {each:g} g each", "named": True, "same": same}
    if k in BUNCHED:
        per = (e.get("units") or {}).get("bunch")
        if per:
            n = max(1, math.ceil(grams / per - 0.15))
            return {"buy": _n(n, "bunch", "bunches"), "note": f"a bunch is about {per:g} g"}
    pc = _pack_choice(grams, e)
    if pc:
        buy, left = pc
        small = _smallest(e)
        if k in STAPLES and small and grams <= 0.15 * small:
            return {"buy": "check the cupboard", "note": f"only {grams:g} g needed; if out, {buy.replace('1 × ', '')}", "check": True}
        return {"buy": buy, "note": _left(left, e)}
    return None
