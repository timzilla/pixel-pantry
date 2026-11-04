"""Recipe extraction with Claude for pages that carry no machine-readable recipe (used only when a key is set)."""
import os, re
from typing import List, Optional
from pydantic import BaseModel


class Recipe(BaseModel):
    title: str
    ingredients: List[str]
    steps: List[str]
    yields: Optional[str] = None
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    total_minutes: Optional[int] = None
    description: Optional[str] = None


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def page_text(html: str, limit: int = 60000) -> str:
    t = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t); t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()[:limit]


def extract(url: str, html: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "low"},
        system="You extract the single main recipe from a web page's text. Copy ingredient lines and steps faithfully, in order, "
               "one ingredient per entry and one step per entry, without commentary. Leave fields you cannot find empty.",
        messages=[{"role": "user", "content": f"Page: {url}\n\n{page_text(html)}"}],
        output_format=Recipe,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise ValueError("Claude could not extract a recipe from this page")
    r = response.parsed_output
    return {"title": r.title, "ingredients": r.ingredients, "steps": r.steps, "yields": r.yields, "prep": r.prep_minutes,
            "cook": r.cook_minutes, "total": r.total_minutes, "description": r.description, "image": None, "how": "claude"}


class Estimate(BaseModel):
    index: int
    grams: Optional[int] = None
    basis: str


class Estimates(BaseModel):
    items: List[Estimate]


def estimate_grams(lines: List[str]) -> dict:
    """Claude's best guess at grams for ingredient lines the weight table could not place. Returns {index: (grams, basis)}.
    Lines that have no sensible weight (to taste, garnish, a spoon of a spice) come back as None."""
    import anthropic
    client = anthropic.Anthropic()
    numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(lines))
    response = client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=4000,
        output_config={"effort": "low"},
        system="You estimate the weight in grams of recipe ingredient lines for a home cook, as written (the stated quantity, not per unit). "
               "Use typical US supermarket sizes. Give grams as a whole number and a basis of a few words (for example '1 medium zucchini ~200 g'). "
               "Give null grams for lines with no quantity, 'to taste', garnishes, and spoon measures of spices or dried herbs. Return one item per line, in order.",
        messages=[{"role": "user", "content": numbered}],
        output_format=Estimates,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None: return {}
    return {it.index: (it.grams, it.basis) for it in response.parsed_output.items if 0 <= it.index < len(lines)}
