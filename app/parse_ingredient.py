"""Split an ingredient line into quantity, unit, name and note, and estimate grams where we can.

"2 cups all-purpose flour, sifted" -> qty 2, unit "cup", name "all-purpose flour", note "sifted", grams 250.
Deliberately simple: regexes for the shape of the line, then weights.grams_for() for the number (see weights.py and
weights.json). The original text is always kept and shown beside any converted number.
"""
import re
import weights

FRACTIONS = {"½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875, "⅕": 0.2}
NUM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+|[½⅓⅔¼¾⅛⅜⅝⅞⅕]|\d+\s*[½⅓⅔¼¾⅛⅜⅝⅞⅕])"
UNITS = {
    "cup": ["cups", "cup", "c."], "tbsp": ["tablespoons", "tablespoon", "tbsps", "tbsp", "tbs", "tb", "T", "tbl"], "tsp": ["teaspoons", "teaspoon", "tsps", "tsp", "t"],
    "fl oz": ["fluid ounces", "fluid ounce", "fl. oz.", "fl oz", "fl.oz", "floz"], "pint": ["pints", "pint", "pt"], "quart": ["quarts", "quart", "qt"], "gallon": ["gallons", "gallon", "gal"],
    "g": ["grams", "gram", "g", "gr"], "kg": ["kilograms", "kilogram", "kg"], "mg": ["milligrams", "mg"], "ml": ["milliliters", "millilitres", "milliliter", "millilitre", "ml", "mL"],
    "l": ["liters", "litres", "liter", "litre", "l", "L"], "oz": ["ounces", "ounce", "oz"], "lb": ["pounds", "pound", "lbs", "lb"],
    "pinch": ["pinches", "pinch"], "dash": ["dashes", "dash"], "drop": ["drops", "drop"], "clove": ["cloves", "clove"], "can": ["cans", "can"], "tin": ["tins", "tin"], "stick": ["sticks", "stick"],
    "slice": ["slices", "slice"], "bunch": ["bunches", "bunch"], "sprig": ["sprigs", "sprig"], "head": ["heads", "head"], "package": ["packages", "package", "pkg", "pkgs"], "pack": ["packs", "pack"],
    "piece": ["pieces", "piece"], "handful": ["handfuls", "handful"], "stalk": ["stalks", "stalk"], "rib": ["ribs", "rib"], "sheet": ["sheets", "sheet"], "fillet": ["fillets", "fillet", "filets", "filet"],
    "ear": ["ears", "ear"], "cob": ["cobs", "cob"], "leaf": ["leaves", "leaf"], "inch": ["inches", "inch", "in."], "knob": ["knobs", "knob"], "thumb": ["thumb-sized piece", "thumb"],
    "packet": ["packets", "packet", "envelopes", "envelope", "sachets", "sachet"], "link": ["links", "link"], "strip": ["strips", "strip"], "rasher": ["rashers", "rasher"],
    "jar": ["jars", "jar"], "bag": ["bags", "bag"], "box": ["boxes", "box"], "bottle": ["bottles", "bottle"], "carton": ["cartons", "carton"], "container": ["containers", "container"], "tub": ["tubs", "tub"],
    "pouch": ["pouches", "pouch"], "tube": ["tubes", "tube"], "block": ["blocks", "block"], "ball": ["balls", "ball"], "loaf": ["loaves", "loaf"], "scoop": ["scoops", "scoop"], "wedge": ["wedges", "wedge"],
    "square": ["squares", "square"], "cube": ["cubes", "cube"], "bar": ["bars", "bar"], "rack": ["racks", "rack"], "ring": ["rings", "ring"], "spear": ["spears", "spear"], "shot": ["shots", "shot"],
    "dozen": ["dozen"], "whole": ["whole"], "splash": ["splashes", "splash"], "drizzle": ["drizzle"], "glug": ["glugs", "glug"], "squeeze": ["squeeze"], "sprinkle": ["sprinkle", "sprinkling"], "half": ["halves", "half"], "pod": ["pods", "pod"], "heart": ["hearts", "heart"], "crown": ["crowns", "crown"],
}
UNIT_LOOKUP = {alias.lower(): u for u, aliases in UNITS.items() for alias in aliases}
UNIT_RE = "|".join(sorted((re.escape(a) for a in UNIT_LOOKUP), key=len, reverse=True))
SIZE_WORDS = {"large", "medium", "small", "big", "extra-large", "extra", "jumbo", "heaping", "heaped", "level", "scant", "generous", "baby", "mini", "thin", "thick", "x-large", "xl"}
JUICE = {"lemon": ("lemon juice", 45, "lemon zest", 6), "lime": ("lime juice", 30, "lime zest", 4), "orange": ("orange juice", 70, "orange zest", 10), "grapefruit": ("grapefruit juice", 150, "zest", 12)}


def _num(tok: str):
    tok = tok.strip()
    if not tok: return None
    total = 0.0
    for part in re.split(r"\s+", tok):
        if part in FRACTIONS: total += FRACTIONS[part]
        elif "/" in part:
            a, b = part.split("/", 1)
            try: total += float(a) / float(b)
            except (ValueError, ZeroDivisionError): return None
        else:
            m = re.match(r"^(\d*\.?\d+)([½⅓⅔¼¾⅛⅜⅝⅞⅕])?$", part)
            if not m: return None
            total += float(m.group(1)) + (FRACTIONS[m.group(2)] if m.group(2) else 0)
    return round(total, 3)


def parse(text: str) -> dict:
    """Returns {text, qty, qty_max, unit, name, note, grams, grams_how}."""
    raw = text.strip()
    s = re.sub(r"\s+", " ", raw)
    s = re.sub(r"^[\-\*•·]\s*", "", s)
    out = {"text": raw, "qty": None, "qty_max": None, "unit": None, "name": s, "note": "", "grams": None, "grams_how": ""}
    jm = re.match(r"^(?:the\s+)?(juice|zest)\s+(?:and\s+zest\s+)?of\s+({NUM}|a|an|one|half a|half an|½)\s+(lemon|lime|orange|grapefruit)s?\b(.*)$".replace("{NUM}", NUM), s, re.I)
    if jm:   # "juice of 1 lemon" -> 1 x lemon juice, 45 g
        n = {"a": 1, "an": 1, "one": 1, "half a": 0.5, "half an": 0.5, "½": 0.5}.get(jm.group(2).lower()) or _num(jm.group(2)) or 1
        name, g, zname, zg = JUICE[jm.group(3).lower()]
        if jm.group(1).lower() == "zest": name, g = zname, zg
        out.update(qty=n, unit=None, name=name, note=f"{jm.group(1).lower()} of {jm.group(2)} {jm.group(3).lower()}{'s' if n != 1 else ''}" + jm.group(4).strip(" ,"))
        out["grams"], out["grams_how"] = weights.grams_for(out)
        return out
    m = re.match(rf"^(?:about |approx\.? |approximately )?({NUM})(?:\s*(?:-|–|to)\s*({NUM}))?\s*(.*)$", s, re.I)
    rest = s
    if m:
        out["qty"] = _num(m.group(1)); out["qty_max"] = _num(m.group(2)) if m.group(2) else None; rest = m.group(3)
    elif re.match(r"^(half an?|half)\s+", s, re.I):   # "half a 340g jar of jam", "half an onion"
        out["qty"] = 0.5; rest = re.sub(r"^(half an?|half)\s+", "", s, flags=re.I)
    elif re.match(r"^(a|an|one)\s+(?!few|little|bit)", s, re.I):   # "a lemon", "an onion"
        out["qty"] = 1.0; rest = re.sub(r"^(a|an|one)\s+", "", s, flags=re.I)
    elif re.match(r"^(pinch|dash|drop|splash|drizzle|glug|handful|knob|sprig|clove|slice|squeeze|sprinkle)(es|s)?\s+(of\s+)?\S", s, re.I):   # "pinch of salt", "drop vanilla"
        out["qty"] = 1.0; rest = s
    um = re.match(rf"^({UNIT_RE})\.?\s+(?:of\s+)?(.*)$", rest, re.I) if out["qty"] is not None else None
    if um and um.group(1).lower() in UNIT_LOOKUP and um.group(2):
        out["unit"] = UNIT_LOOKUP[um.group(1).lower()]; rest = um.group(2)
    else:  # "(14 oz) can", "8-ounce package": a parenthetical or hyphenated size before a container unit
        pm = re.match(rf"^\(?({NUM})[\s-]*({UNIT_RE})\.?\)?\s+({UNIT_RE})s?\s+(?:of\s+)?(.*)$", rest, re.I)
        if pm and pm.group(3).lower() in UNIT_LOOKUP:
            out["unit"] = UNIT_LOOKUP[pm.group(3).lower()]; out["note"] = f"{pm.group(1)} {pm.group(2)} each"; rest = pm.group(4)
        else:
            pm = re.match(rf"^\(([^)]*)\)\s+({UNIT_RE})s?\s+(?:of\s+)?(.*)$", rest, re.I)   # "(14.5oz; 410g) can crushed tomatoes"
            if pm and pm.group(2).lower() in UNIT_LOOKUP and out["qty"] is not None:
                out["unit"] = UNIT_LOOKUP[pm.group(2).lower()]; out["note"] = pm.group(1).strip() + " each"; rest = pm.group(3)
    name, note = rest, out["note"]
    if "," in name:
        name, extra = name.split(",", 1); note = (note + "; " if note else "") + extra.strip()
    while True:   # every parenthetical goes to the note: "(or plain flour)", "(710ml)"; an unclosed one too
        pm = re.search(r"\(([^)]*)(?:\)|$)", name)
        if not pm: break
        note = (note + "; " if note else "") + pm.group(1).strip(" ,;"); name = (name[:pm.start()] + name[pm.end():]).strip()
    words = name.split()
    while words and words[0].lower() in SIZE_WORDS: note = (words[0] + ("; " + note if note else "")); words = words[1:]
    name = " ".join(words).strip(" .")
    out["name"], out["note"] = name or s, note.strip("; ")
    out["grams"], out["grams_how"] = weights.grams_for(out)
    return out
