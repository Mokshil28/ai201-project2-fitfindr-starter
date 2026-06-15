# FitFindr 🛍️

FitFindr is a thrift-shopping agent. You describe what you want in plain English
("vintage graphic tee under $30"), and it searches a mock secondhand-listings
dataset, styles the best find against your existing wardrobe, and writes a
shareable social-media caption for the look — all in one interaction.

It is built as a small **planning-loop agent**: a deterministic loop orchestrates
three tools, passing state between them and branching when a step fails.

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file in the project root (free key at
[console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Then open the URL printed in your terminal (usually
http://localhost:7860 — check the output, the port can differ).

Run the tests:

```bash
python -m pytest tests/
```

---

## How it works (the planning loop)

The agent's brain is `run_agent(query, wardrobe)` in [`agent.py`](agent.py). It is
**not** an LLM deciding what to do next — it is a fixed, auditable pipeline with a
single decision point. This matters: the agent behaves *differently* depending on
what the search returns, rather than blindly calling all three tools every time.

```
User query
    │  _parse_query()  → description, size, max_price   (regex, not an LLM)
    ▼
search_listings(description, size, max_price)
    │
    ├── results == []  ──►  set session["error"]  ──►  RETURN EARLY
    │                       (suggest_outfit / create_fit_card are NEVER called)
    │
    └── results == [item, ...]
            │  session["selected_item"] = results[0]   (top relevance match)
            ▼
        suggest_outfit(selected_item, wardrobe)
            │  session["outfit_suggestion"] = "..."
            ▼
        create_fit_card(outfit_suggestion, selected_item)
            │  session["fit_card"] = "..."
            ▼
        RETURN session
```

**The one decision the agent makes:** after `search_listings`, is the result list
empty? If yes, it stops and tells the user how to adjust their query. If no, it
selects the top result and continues. There are no other branches — the rest is a
straight pipeline — but that single branch is what makes it a real planning loop
rather than a hardcoded script.

**Why regex for query parsing?** The parsing targets are simple, bounded patterns
(a `under $N` / `$N` price phrase and a `size X` phrase), so a deterministic regex
parser is faster, free, and unit-testable — no LLM call needed. Filler words
("looking for a…") are stripped so they don't pollute search relevance.

---

## State management

All information for one interaction lives in a single `session` dict, created by
`_new_session()` and threaded through the pipeline. Each tool reads its inputs
from `session` and the loop writes each tool's output back, so the next tool can
pick it up. **No tool calls another tool directly**, and nothing is re-prompted or
hardcoded between steps — the loop is the only thing that reads/writes state.

| Session key | Set by | Read by |
|---|---|---|
| `query` | caller | `_parse_query` |
| `parsed` (`description`, `size`, `max_price`) | `_parse_query` | `search_listings` |
| `wardrobe` | caller (`get_example_wardrobe()` / `get_empty_wardrobe()`) | `suggest_outfit` |
| `search_results` | `search_listings` | planning loop (empty check) |
| `selected_item` | planning loop (`= search_results[0]`) | `suggest_outfit`, `create_fit_card` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | final output |
| `error` | planning loop (on empty results) | final output |

The critical handoff chain: `search_listings → selected_item → suggest_outfit →
outfit_suggestion → create_fit_card`. The **same** `selected_item` dict is passed
into both `suggest_outfit` and `create_fit_card` — verified during testing by
printing `session["selected_item"]` and confirming it is the item that appears in
both the outfit suggestion and the fit card.

---

## Tool inventory

### 1. `search_listings(description, size, max_price) → list[dict]`

**Purpose:** Find listings matching the user's keywords, size, and budget.

| Parameter | Type | Meaning |
|---|---|---|
| `description` | `str` | Keywords, e.g. `"vintage graphic tee"`. Scored by whole-word overlap against each listing's title, description, and `style_tags` (stopwords removed). |
| `size` | `str \| None` | Size filter, e.g. `"M"`. Case-insensitive substring match, so `"M"` matches `"S/M"`. `None` skips size filtering. |
| `max_price` | `float \| None` | Inclusive price ceiling. `None` skips price filtering. |

**Returns:** A `list[dict]` of full listing dicts (`id`, `title`, `description`,
`category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`,
`platform`), sorted by relevance, best first. Returns `[]` if nothing matches —
**never raises**.

### 2. `suggest_outfit(new_item, wardrobe) → str`

**Purpose:** Style the chosen item using the user's wardrobe (LLM-backed —
Groq `llama-3.3-70b-versatile`).

| Parameter | Type | Meaning |
|---|---|---|
| `new_item` | `dict` | The selected listing dict to style. |
| `wardrobe` | `dict` | `{"items": [...]}`; each item has `id`, `name`, `category`, `colors`, `style_tags`, optional `notes`. May be empty. |

**Returns:** A non-empty `str` of styling advice. With a populated wardrobe it
names real owned pieces; with an empty wardrobe it gives general styling advice.

### 3. `create_fit_card(outfit, new_item) → str`

**Purpose:** Write a short, casual, shareable OOTD caption (LLM-backed, higher
temperature so repeated calls vary).

| Parameter | Type | Meaning |
|---|---|---|
| `outfit` | `str` | The styling text from `suggest_outfit`. |
| `new_item` | `dict` | The selected listing dict — its title, price, and platform are woven into the caption. |

**Returns:** A 2–4 sentence caption `str` mentioning item name, price, and
platform once each. If `outfit` is empty/whitespace, returns a descriptive error
string instead.

---

## Error handling

Every failure mode was triggered deliberately (see
[`docs/failure-modes.md`](docs/failure-modes.md)) and is covered by tests in
[`tests/test_tools.py`](tests/test_tools.py).

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | No listing matches | Returns `[]` (no exception). The loop sets `session["error"]` and returns early, **without** calling the other two tools. |
| `suggest_outfit` | Wardrobe is empty | Falls back to general styling advice — never empty, never raises. (Also: if the LLM call itself errors, returns a simple fallback string so the pipeline can continue.) |
| `create_fit_card` | Outfit string missing/blank | Returns `"I need an outfit suggestion before I can write a fit card — let's style the item first."` — a descriptive string, not an exception. |

**Concrete example from testing** — running the agent on the impossible query
`"designer ballgown size XXS under $5"`:

```
error      : No matches for 'designer ballgown' under $5 in size XXS. Try raising
             your budget, removing the size filter, or using broader keywords.
fit_card   : None
selected   : None
```

The error message is specific and actionable (it names the query, the price, and
the size, and suggests what to change), and the LLM tools are provably never
reached — `selected_item` and `fit_card` are both `None`.

---

## AI usage

I used **Claude (Claude Code)** throughout, driven by my `planning.md` spec. Two
specific instances:

**1. Implementing `search_listings`.** I gave Claude the Tool 1 block from
`planning.md` (the three parameters with types, the scored-and-sorted return
contract, and the empty-list failure mode) plus the `load_listings()` docstring.
It produced a working filter-score-sort function. **What I changed:** the first
version scored relevance with `str.count()`, which counts *substrings* — so the
single letter `"a"` from filler words like "looking for a" was counted letter by
letter and dominated the score, surfacing the wrong item (a knit vest instead of
a graphic tee). I overrode this with **whole-word matching plus a stopword list**
and refactored scoring into a `_relevance_score()` helper, then added a regression
test (`test_search_ignores_filler_words`) so it can't silently come back.

**2. Implementing the planning loop.** I gave Claude the Planning Loop, State
Management, and Architecture (ASCII diagram) sections from `planning.md`. It
produced `run_agent()` wiring the three tools through the `session` dict with the
empty-results early return. **What I verified/changed:** I traced the generated
code against my diagram to confirm it returns early on `[]` *before* calling the
LLM tools and that `selected_item = results[0]` is threaded into both downstream
tools. I also chose **regex over an LLM for query parsing** (Claude offered both)
because the patterns are simple and I wanted parsing to be deterministic and
testable.

---

## Spec reflection

Building from `planning.md` first paid off: because each tool's inputs, return
type, and failure mode were specified before any code, the tools dropped into the
planning loop without rework, and the failure-mode tests in Milestone 5 passed on
the first try. The one place reality diverged from the spec was relevance scoring
— the plan said "score by keyword overlap" but didn't specify *word* vs.
*substring* overlap, and that ambiguity is exactly where the filler-word bug crept
in. The lesson: a spec that's precise about data shapes still needs to be precise
about *algorithms* where correctness depends on the details.

---

## Project structure

```
ai201-project2-fitfindr-starter/
├── agent.py                 # Planning loop: _parse_query() + run_agent()
├── app.py                   # Gradio UI + handle_query()
├── tools.py                 # The 3 tools + relevance-scoring helpers
├── planning.md              # Design spec (written before the code)
├── data/
│   ├── listings.json        # 40 mock secondhand listings
│   └── wardrobe_schema.json # Wardrobe format + example/empty wardrobes
├── utils/
│   └── data_loader.py       # load_listings(), get_example_wardrobe(), ...
├── tests/
│   └── test_tools.py        # 12 tests incl. every failure mode
├── docs/
│   └── failure-modes.md     # Triggered failures (Milestone 5)
└── conftest.py              # Puts project root on sys.path for pytest
```
