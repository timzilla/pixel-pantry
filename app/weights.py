"""Grams for an ingredient line, from the weight table in weights.json plus a few rules.

match(text) finds the table entry whose longest phrase appears in the ingredient name (so "green onion" beats "onion",
"cream cheese" beats "cream"). grams_for(ing) then turns qty + unit into grams: weight units directly, volumes through
the entry's grams-per-cup, counts through grams-per-piece (with small/medium/large), named units (clove, slice, stick,
bunch...) through the entry's unit table, and cans/jars through the size in the note or the entry's default can.
Spices and dried herbs are never weighed. Everything returns (grams, how) where `how` says where the number came from.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
CUP_ML = 236.6
VOLUME_CUPS = {"cup": 1, "tbsp": 1 / 16, "tsp": 1 / 48, "pint": 2, "quart": 4, "gallon": 16, "fl oz": 1 / 8, "splash": 1 / 16, "drizzle": 1 / 16, "glug": 1 / 8, "squeeze": 1 / 16, "sprinkle": 1 / 48}
WEIGHT_G = {"g": 1, "kg": 1000, "mg": 0.001, "oz": 28.35, "lb": 453.6}
CONTAINER_DEFAULT = {"can": 425, "tin": 425, "jar": 454, "bottle": 355, "carton": 946}
CONTAINER_WORDS = {"can", "tin", "jar", "bottle", "carton", "package", "pack", "bag", "box", "container", "tub", "pouch", "tube", "envelope", "packet", "sachet"}
UNIT_DEFAULT = {"clove": 5, "stick": 113, "slice": 28, "bunch": 60, "sprig": 1, "stalk": 40, "rib": 40, "ear": 103, "cob": 103, "inch": 10, "knob": 30, "thumb": 30,
                "link": 85, "strip": 28, "rasher": 28, "fillet": 150, "filet": 150, "cube": 4, "scoop": 30, "handful": 30, "square": 28, "wedge": 10, "shot": 44,
                "packet": 7, "sheet": None, "head": None, "leaf": None, "ball": None, "loaf": None, "block": None, "rack": None, "bar": None, "ring": None, "spear": 16, "pod": None, "cake": None, "heart": None, "crown": None, "half": None, "piece": None}
SIZE_ALIASES = {"big": "large", "xl": "extra-large", "extra large": "extra-large", "x-large": "extra-large", "extra-large": "extra-large", "jumbo": "jumbo", "small": "small", "medium": "medium", "large": "large",
                "baby": "baby", "mini": "mini", "thin": "thin", "thick": "thick", "new": "new", "fingerling": "fingerling", "medjool": "medjool", "deglet": "deglet", "persian": "persian", "colossal": "colossal",
                "ataulfo": "ataulfo", "champagne": "champagne", "mandarin": "mandarin", "clementine": "clementine", "apricot": "apricot", "spear": "spear", "cornichon": "cornichon"}

with open(os.path.join(HERE, "weights.json"), encoding="utf-8") as f:
    TABLE = json.load(f)


def _sing(w):
    if len(w) <= 3 or w.endswith("ss") or w.endswith("us"): return w
    if w.endswith("ies"): return w[:-3] + "y"
    if w.endswith("oes") and len(w) > 4: return w[:-2]
    if w.endswith(("ches", "shes", "sses", "xes", "zes")): return w[:-2]
    if w.endswith("s"): return w[:-1]
    return w


def norm(s):
    s = s.lower().replace("-", " ").replace("’", "'").replace("'", "")
    s = re.sub(r"[^a-z0-9&%/ ]+", " ", s)
    return " ".join(_sing(w) for w in s.split())


PHRASES = []   # (normalized phrase, word count, entry, original phrase)
for _e in TABLE["entries"]:
    for _p in _e["m"]:
        _n = norm(_p)
        if _n: PHRASES.append((_n, len(_n.split()), _e, _p))
PHRASES.sort(key=lambda t: (-t[1], -len(t[0])))


def match(text):
    """Best (entry, phrase) for an ingredient name, or (None, None)."""
    n = " " + norm(text) + " "
    if not n.strip(): return None, None
    for p, _, e, orig in PHRASES:
        if " " + p + " " in n: return e, orig
    return None, None


def _find(name, note):
    """Best entry for the name, or (None, None). See candidates()."""
    c = candidates(name, note)
    return c[0] if c else (None, None)


def candidates(name, note):
    """Entries that could describe this ingredient, best first: the name as written, then qualified by words from the
    note or name ('dried', 'bone-in', 'chopped'...), then the note itself (for '2 cups all-purpose (or plain flour)')."""
    low = (name + " " + note).lower()
    tries = [name]
    for q in ("dried", "ground", "fresh", "cooked", "canned", "frozen", "bone-in", "bone in", "boneless", "skinless", "shredded", "grated", "sliced", "chopped", "minced", "mashed", "melted", "roasted", "smoked"):
        if q in low and not name.lower().startswith(q): tries.append(q + " " + name)
    found = []
    for t in tries:
        e, p = match(t)
        if e and all(e is not f for f, _ in found): found.append((e, p))
    found.sort(key=lambda ep: (len(norm(ep[1]).split()), len(ep[1])), reverse=True)
    if not found and note:
        e, p = match(note)
        if e: found.append((e, p))
    return found


def _size(note, entry):
    sizes = entry.get("sizes") or {}
    for w in re.split(r"[;,\s]+", note.lower()):
        k = SIZE_ALIASES.get(w)
        if k and k in sizes: return k, sizes[k]
    return None, None


def _per_cup(e):
    if e.get("cup"): return e["cup"]
    if e.get("tbsp"): return e["tbsp"] * 16
    if e.get("tsp"): return e["tsp"] * 48
    return None


def _container_grams(note):
    low = note.lower()
    m = re.search(r"(\d+(?:\.\d+)?)[\s-]*(g|gram|grams)\b", low) or re.search(r"(\d+(?:\.\d+)?)[\s-]*(fl\.? ?oz|oz|ounce|ounces|ml|lb|pound|pounds|kg|l|liter|litre)\b", low)
    if not m: return None, None
    n, u = float(m.group(1)), m.group(2)
    if u.startswith("fl"): return round(n * 29.57), f"{n:g} fl oz"
    if u in ("oz", "ounce", "ounces"): return round(n * 28.35), f"{n:g} oz"
    if u in ("lb", "pound", "pounds"): return round(n * 453.6), f"{n:g} lb"
    if u in ("kg",): return round(n * 1000), f"{n:g} kg"
    if u in ("l", "liter", "litre"): return round(n * 1000), f"{n:g} l"
    if u == "ml": return round(n), f"{n:g} ml"
    return round(n), f"{n:g} g"


HERB_UNITS = {"sprig", "bunch", "leaf", "stalk", "handful", "stem"}


def _round(g):
    if g is None: return None
    if g < 0.05: return None
    return round(g, 1) if g < 10 else round(g)


def grams_for(ing):
    g, how = _grams_for(ing)
    return _round(g), how


def _grams_for(ing):
    qty, unit, name, note = ing.get("qty"), ing.get("unit"), (ing.get("name") or ""), (ing.get("note") or "")
    if qty is None or not name: return None, ""
    if unit == "dozen": qty, unit = qty * 12, None
    if unit in WEIGHT_G: return qty * WEIGHT_G[unit], ("as written" if unit in ("g", "kg") else f"1 {unit} = {WEIGHT_G[unit]:g} g")
    cands = candidates(name, note)
    if cands and cands[0][0].get("spice") and (unit in HERB_UNITS or unit is None):   # "2 sprigs rosemary": the fresh herb, not the jar
        e2, p2 = match("fresh " + name)
        if e2 and not e2.get("spice"): cands.insert(0, (e2, p2))
    if not cands: cands = [(None, None)]
    last = (None, "")
    for e, phrase in cands:
        g, how = _resolve(qty, unit, name, note, e, phrase)
        if g is not None or how == "spice, not weighed": return g, how
        if how and not last[1]: last = (g, how)
    if last[1]: return last
    d = UNIT_DEFAULT.get(unit)
    if d and cands[0][0] is not None: return qty * d, f"typical {unit}: {d:g} g"
    return None, ""


def _resolve(qty, unit, name, note, e, phrase):
    src = f" ({e['src']})" if e else ""
    if unit in ("ml", "l"):
        ml = qty * (1000 if unit == "l" else 1)
        d = (e or {}).get("dens") or ((_per_cup(e) / CUP_ML) if e and _per_cup(e) else 1.0)
        return ml * d, f"{ml:g} ml at {d:.2f} g/ml" + (f" for {phrase}{src}" if e else "")
    if e is None:
        if unit in CONTAINER_WORDS:
            g, how = _container_grams(note)
            if g: return qty * g, f"{how} {unit}"
        return None, ""
    if e.get("spice"): return None, "spice, not weighed"
    if unit in VOLUME_CUPS:
        if unit == "tbsp" and e.get("tbsp"): return qty * e["tbsp"], f"{e['tbsp']:g} g per tablespoon of {phrase}{src}"
        if unit == "tsp" and e.get("tsp"): return qty * e["tsp"], f"{e['tsp']:g} g per teaspoon of {phrase}{src}"
        if unit == "tsp" and e.get("tbsp"): return qty * e["tbsp"] / 3, f"{e['tbsp']:g} g per tablespoon of {phrase}{src}"
        pc = _per_cup(e)
        if pc is None: return None, ""
        return qty * VOLUME_CUPS[unit] * pc, f"{pc:g} g per cup of {phrase}{src}"
    if unit in ("pinch", "dash", "drop"):
        tsp = e.get("tsp") or (e.get("tbsp") / 3 if e.get("tbsp") else (e["cup"] / 48 if e.get("cup") else None))
        if tsp is None: return None, ""
        g = qty * tsp * {"pinch": 1 / 16, "dash": 1 / 8, "drop": 1 / 100}[unit]
        return g, f"a {unit} is 1/{ {'pinch': 16, 'dash': 8, 'drop': 100}[unit] } teaspoon of {phrase}{src}"
    if unit in (None, "piece", "whole"):
        g, how = _container_grams(note)
        if g: return qty * g, f"{how} each, as written"
        units = e.get("units") or {}
        if unit == "piece" and units.get("piece"): return qty * units["piece"], f"{units['piece']:g} g per piece of {phrase}{src}"
        sz, g = _size(note, e)
        if g: return qty * g, f"about {g:g} g each ({sz}), {phrase}{src}"
        if e.get("each"): return qty * e["each"], f"about {e['each']:g} g each, {phrase}{src}" + (f"; {e['note']}" if e.get("note") else "")
        return None, ""
    if unit in CONTAINER_WORDS:
        g, how = _container_grams(note)
        if g: return qty * g, f"{how} {unit} of {phrase}"
        units = e.get("units") or {}
        if units.get(unit): return qty * units[unit], f"{units[unit]:g} g per {unit} of {phrase}{src}" + (f"; {e['note']}" if e.get("note") and unit in e["note"] else "")
        if unit in CONTAINER_DEFAULT: return qty * CONTAINER_DEFAULT[unit], f"assumed a {CONTAINER_DEFAULT[unit]} g ({ {425: '15 oz', 454: '16 oz', 355: '12 oz', 946: '32 oz'}[CONTAINER_DEFAULT[unit]] }) {unit} of {phrase}"
        return None, ""
    units = e.get("units") or {}
    if units.get(unit): return qty * units[unit], f"{units[unit]:g} g per {unit} of {phrase}{src}"
    return None, ""


def reweigh(ings):
    """Re-parse each ingredient from its original text with the current parser and table, in place.
    Keeps a Claude estimate where the table still has nothing. Returns True if anything changed."""
    from parse_ingredient import parse
    changed = False
    for i in ings:
        new = parse(i.get("text") or i.get("name") or "")
        if new["grams"] is None and i.get("grams_est") and i.get("grams") is not None:
            new["grams"], new["grams_how"], new["grams_est"] = i["grams"], i["grams_how"], True
        if any(new.get(k) != i.get(k) for k in ("qty", "qty_max", "unit", "name", "note", "grams", "grams_how", "grams_est")):
            i.clear(); i.update(new); changed = True
    return changed


def needs_estimate(i):
    return i.get("grams") is None and i.get("qty") is not None and i.get("grams_how") != "spice, not weighed"


def fill_missing(ings, ask_claude=True):
    """For ingredients the table could not weigh, ask Claude (if a key is set). Marks them grams_est so the page shows a tilde."""
    import claude_fallback
    todo = [k for k, i in enumerate(ings) if needs_estimate(i)]
    if not todo or not ask_claude or not claude_fallback.available(): return False
    try: est = claude_fallback.estimate_grams([ings[k]["text"] for k in todo])
    except Exception: return False
    changed = False
    for j, k in enumerate(todo):
        g, basis = est.get(j, (None, ""))
        if g: ings[k]["grams"], ings[k]["grams_how"], ings[k]["grams_est"] = int(g), f"Claude's estimate: {basis}", True; changed = True
        elif basis: ings[k]["grams_how"] = f"not weighed: {basis}"; changed = True
    return changed
