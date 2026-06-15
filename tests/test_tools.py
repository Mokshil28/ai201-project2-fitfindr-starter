"""
Tests for the three FitFindr tools, each tested in isolation.

At least one test per failure mode:
- search_listings  -> returns [] (no exception) when nothing matches
- suggest_outfit   -> returns general advice (non-empty str) when wardrobe empty
- create_fit_card  -> returns an error string when the outfit is missing

The LLM-backed tools (suggest_outfit, create_fit_card) are written so they
return a non-empty fallback string if no GROQ_API_KEY is set, so these tests
pass with or without a live API key.
"""

from tools import (
    search_listings,
    suggest_outfit,
    create_fit_card,
    _relevance_score,
    _keywords,
)
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Nonsense query well under any real price -> no matches, empty list.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []  # empty list, not an exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_is_case_insensitive_substring():
    # "m" should match sizes like "M", "S/M", "M/L".
    results = search_listings("tee", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance_descending():
    # Results must come back in non-increasing relevance order. Re-score with
    # the same helper the implementation uses to avoid coupling to internals.
    results = search_listings("vintage denim", size=None, max_price=None)
    assert len(results) >= 2
    keywords = _keywords("vintage denim")
    scores = [_relevance_score(r, keywords) for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_ignores_filler_words():
    # "looking for a" is filler — the top result for a graphic-tee query should
    # be an actual graphic tee, not whatever has the most stray 'a' characters.
    results = search_listings(
        "looking for a vintage graphic tee", size=None, max_price=30
    )
    assert len(results) > 0
    assert "graphic tee" in results[0]["style_tags"]


def test_search_returns_full_listing_dicts():
    results = search_listings("vintage", size=None, max_price=None)
    expected_fields = {
        "id", "title", "description", "category", "style_tags",
        "size", "condition", "price", "colors", "brand", "platform",
    }
    assert expected_fields.issubset(results[0].keys())


# ── suggest_outfit ────────────────────────────────────────────────────────────

def _sample_item():
    # A real listing to style (a graphic tee).
    listings = load_listings()
    return next(item for item in listings if "graphic tee" in item["style_tags"])


def test_suggest_outfit_with_wardrobe_returns_nonempty():
    result = suggest_outfit(_sample_item(), get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_empty_wardrobe_does_not_crash():
    # Failure mode: empty wardrobe -> general advice, never crashes or empty.
    result = suggest_outfit(_sample_item(), get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_message():
    # Failure mode: missing/incomplete outfit -> descriptive error string.
    result = create_fit_card("", _sample_item())
    assert isinstance(result, str)
    assert "outfit" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_message():
    result = create_fit_card("   \n  ", _sample_item())
    assert isinstance(result, str)
    assert "outfit" in result.lower()


def test_create_fit_card_with_outfit_returns_nonempty():
    result = create_fit_card(
        "Pair it with baggy jeans and chunky sneakers.", _sample_item()
    )
    assert isinstance(result, str)
    assert result.strip() != ""
