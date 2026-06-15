"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── relevance scoring ─────────────────────────────────────────────────────────

# Common filler words that carry no search signal. Dropping them stops queries
# like "looking for a vintage tee" from being dominated by "a"/"for".
_STOPWORDS = {
    "a", "an", "the", "for", "and", "or", "of", "to", "in", "on", "with",
    "my", "me", "i", "im", "i'm", "is", "it", "looking", "look", "want",
    "wanting", "need", "find", "finding", "some", "any", "that", "this",
    "under", "below", "size",
}


def _relevance_score(item: dict, keywords: list[str]) -> int:
    """
    Score a listing by how many times the query keywords appear, as whole
    words, across its title, description, and style_tags.
    """
    haystack = " ".join(
        [item["title"], item["description"], " ".join(item["style_tags"])]
    ).lower()
    score = 0
    for kw in keywords:
        score += len(re.findall(rf"\b{re.escape(kw)}\b", haystack))
    return score


def _keywords(description: str) -> list[str]:
    """Tokenize a description into meaningful (non-stopword) lowercase keywords."""
    tokens = re.findall(r"[a-z0-9']+", description.lower())
    return [t for t in tokens if t not in _STOPWORDS]


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Meaningful keyword tokens (stopwords removed).
    keywords = _keywords(description)

    size_filter = size.lower().strip() if size else None

    scored: list[tuple[int, dict]] = []
    for item in listings:
        # 1. Price filter (inclusive).
        if max_price is not None and item["price"] > max_price:
            continue

        # 2. Size filter — case-insensitive substring match so "M" matches
        #    "S/M", "M/L", etc. Skipped entirely when size is None.
        if size_filter is not None and size_filter not in item["size"].lower():
            continue

        # 3. Score by whole-word keyword overlap across title/description/tags.
        score = _relevance_score(item, keywords)

        # 4. Drop listings with no keyword relevance.
        if score > 0:
            scored.append((score, item))

    # 5. Sort by score, highest first, and return just the listing dicts.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_desc = (
        f"{new_item['title']} "
        f"(category: {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])})"
    )

    items = wardrobe.get("items", [])

    if not items:
        # Empty wardrobe — ask for general styling advice for the item alone.
        prompt = (
            f"A shopper is considering this secondhand item:\n{item_desc}\n\n"
            "They haven't told us what's in their closet yet. Suggest how to "
            "style this piece in general terms: what kinds of items pair well "
            "with it, what colors complement it, and what overall vibe or "
            "occasion it suits. Keep it to 2-3 friendly sentences."
        )
    else:
        # Non-empty wardrobe — style the item using specific owned pieces.
        wardrobe_lines = "\n".join(
            f"- {it['name']} ({it['category']}, {', '.join(it['colors'])})"
            for it in items
        )
        prompt = (
            f"A shopper is considering this secondhand item:\n{item_desc}\n\n"
            f"Here is their current wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific "
            "pieces from their wardrobe. Refer to the wardrobe pieces by name. "
            "Keep it to 2-4 friendly, concrete sentences with a styling tip."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are FitFindr, a warm, knowledgeable "
                    "personal stylist who gives concrete, wearable advice.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        # LLM/network failure — return a simple non-empty fallback so the
        # pipeline can still proceed to create_fit_card.
        return (
            f"Style your {new_item['title']} with neutral basics in "
            f"{', '.join(new_item['colors'])} tones for an easy, balanced look."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty/whitespace-only outfit.
    if not outfit or not outfit.strip():
        return (
            "I need an outfit suggestion before I can write a fit card — "
            "let's style the item first."
        )

    title = new_item["title"]
    price = new_item["price"]
    platform = new_item["platform"]

    prompt = (
        f"Write a short, casual social-media caption (Instagram/TikTok OOTD "
        f"style) for a thrifted find.\n\n"
        f"Item: {title}\n"
        f"Price: ${price:.0f}\n"
        f"Platform: {platform}\n"
        f"Outfit it's styled in: {outfit}\n\n"
        "Rules: 2-4 sentences. Sound like a real person posting their outfit, "
        "not a product listing. Mention the item name, price, and platform "
        "naturally — each exactly once. Capture the outfit's vibe in specific "
        "terms. Emojis are welcome but optional."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You write fun, authentic thrift-haul captions "
                    "for social media.",
                },
                {"role": "user", "content": prompt},
            ],
            # Higher temperature so repeated calls on the same input vary.
            temperature=1.0,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        # LLM/network failure — return a simple usable fallback caption.
        return (
            f"thrifted this {title} off {platform} for ${price:.0f} and i'm "
            f"obsessed 🫶 styled it exactly how i pictured."
        )
