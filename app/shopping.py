"""The shopping list: one JSON file, shared by every device. Items merge by ingredient when the unit matches."""
import os, re, json, time, threading
import store

PATH = os.path.join(store.DATA, "shopping.json")
LOCK = threading.Lock()
STRIP = {"softened", "melted", "beaten", "chopped", "finely", "roughly", "diced", "sliced", "minced", "grated", "shredded", "sifted", "fresh",
         "large", "medium", "small", "ripe", "peeled", "cold", "warm", "room", "temperature", "unsalted", "salted", "good-quality", "plus", "extra",
         "to", "taste", "for", "serving", "optional", "divided", "packed", "lightly", "freshly", "ground", "whole", "boneless", "skinless"}
AISLES = [
    ("Produce", ["onion", "garlic", "shallot", "leek", "carrot", "celery", "potato", "tomato", "pepper", "chili", "chilli", "lemon", "lime", "orange", "apple", "banana",
                 "berry", "berries", "avocado", "lettuce", "spinach", "kale", "cabbage", "broccoli", "cauliflower", "zucchini", "courgette", "squash", "mushroom",
                 "herb", "parsley", "cilantro", "coriander", "basil", "thyme", "rosemary", "mint", "dill", "ginger", "scallion", "spring onion", "cucumber", "corn", "pea"]),
    ("Dairy & eggs", ["milk", "butter", "cream", "cheese", "cheddar", "parmesan", "mozzarella", "yogurt", "yoghurt", "egg", "ricotta", "mascarpone"]),
    ("Meat & fish", ["chicken", "beef", "pork", "lamb", "turkey", "bacon", "sausage", "ham", "steak", "mince", "fish", "salmon", "cod", "tuna", "shrimp", "prawn", "anchov"]),
    ("Bakery", ["bread", "bun", "roll", "tortilla", "pita", "naan", "baguette", "croissant"]),
    ("Pantry", ["flour", "sugar", "rice", "pasta", "noodle", "oat", "lentil", "bean", "chickpea", "stock", "broth", "oil", "vinegar", "soy", "sauce", "paste",
                "honey", "syrup", "vanilla", "baking", "yeast", "cocoa", "chocolate", "nut", "almond", "walnut", "pecan", "seed", "coconut", "jam", "can", "tin", "crumb", "panko"]),
    ("Spices", ["salt", "pepper", "cumin", "paprika", "cinnamon", "nutmeg", "oregano", "chili powder", "curry", "turmeric", "cayenne", "spice", "clove", "bay"]),
    ("Frozen", ["frozen", "ice cream"]),
]


def _load():
    try: return json.load(open(PATH))
    except Exception: return {"items": []}


def _save(d):
    tmp = PATH + ".tmp"; json.dump(d, open(tmp, "w"), indent=1); os.replace(tmp, PATH)


def norm(name: str) -> str:
    words = [w for w in re.sub(r"[^a-z0-9 \-]", " ", name.lower()).split() if w not in STRIP]
    s = " ".join(words)
    return re.sub(r"(e?s)$", "", s) if len(s) > 3 and not s.endswith("ss") else s


PANTRY_FIRST = ("crushed tomato", "diced tomato", "canned", "can ", "tomato sauce", "chiles", "vinegar", "paste", "broth", "stock", "sauce", "canned", "dried", "powder", "extract", "syrup", "oil", "bouillon", "jam", "jelly", "chips", "flakes")


def aisle(name: str) -> str:
    n = name.lower()
    if "frozen" in n: return "Frozen"
    try:
        import weights
        e, _ = weights.match(name)
        if e and e.get("spice"): return "Spices"
    except Exception: pass
    if any(w in n for w in PANTRY_FIRST) and not any(w in n for w in ("ice cream",)): return "Pantry"
    for a, keys in AISLES:
        if any(k in n for k in keys): return a
    return "Other"


def items():
    d = _load()
    order = {a: i for i, (a, _) in enumerate(AISLES)}; order["Other"] = 99
    for i in d["items"]: i["aisle"] = aisle(i["name"])   # re-sort old items with the current rules
    return sorted(d["items"], key=lambda i: (i["done"], order.get(i["aisle"], 99), i["name"].lower()))


def add(name: str, qty=None, unit=None, grams=None, source=None):
    with LOCK:
        d = _load(); key = norm(name)
        for it in d["items"]:
            same = it["key"] == key or it["key"].endswith(" " + key) or key.endswith(" " + it["key"])  # "kerrygold butter" ~ "butter"
            by_weight = same and not it["done"] and (it.get("unit") or "") != (unit or "") and grams is not None and it.get("grams") is not None
            if by_weight:   # different units, both weighed: keep one line in grams
                it["grams"] = round(it["grams"] + grams); it["qty"], it["unit"] = None, None
                if len(key) < len(it["key"]): it["name"], it["key"] = name.strip(), key
                if source and source not in it["from"]: it["from"].append(source)
                _save(d); return it["id"]
            if same and (it.get("unit") or "") == (unit or "") and not it["done"]:
                if len(key) < len(it["key"]): it["name"], it["key"] = name.strip(), key  # keep the plainer name
                if qty is not None and it.get("qty") is not None: it["qty"] = round(it["qty"] + qty, 2)
                elif qty is not None: it["qty"] = qty
                if grams is not None and it.get("grams") is not None: it["grams"] = round(it["grams"] + grams)
                elif grams is not None: it["grams"] = grams
                if source and source not in it["from"]: it["from"].append(source)
                _save(d); return it["id"]
        it = {"id": f"{int(time.time() * 1000)}{len(d['items'])}", "name": name.strip(), "key": key, "qty": qty, "unit": unit, "grams": grams,
              "from": [source] if source else [], "done": False, "aisle": aisle(name), "added": time.strftime("%Y-%m-%dT%H:%M:%S")}
        d["items"].append(it); _save(d); return it["id"]


def set_done(item_id: str, done: bool):
    with LOCK:
        d = _load()
        for it in d["items"]:
            if it["id"] == item_id: it["done"] = done
        _save(d)


def remove(item_id: str):
    with LOCK:
        d = _load(); d["items"] = [i for i in d["items"] if i["id"] != item_id]; _save(d)


def clear(done_only=True):
    with LOCK:
        d = _load(); d["items"] = [i for i in d["items"] if done_only and not i["done"]]; _save(d)


def count():
    return sum(1 for i in _load()["items"] if not i["done"])
