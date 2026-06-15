# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock secondhand-listings dataset (loaded via `load_listings()`) for items that match the user's keywords, optional size, and optional price ceiling. It filters out anything over budget or in the wrong size, scores the rest by keyword overlap against the description, drops zero-score items, and returns the matches sorted best-first.

**Input parameters:**
- `description` (str): Free-text keywords describing the desired item, e.g. `"vintage graphic tee"`. Scored against each listing's `title`, `description`, and `style_tags`.
- `size` (str | None): Size to filter by, e.g. `"M"`. Matching is case-insensitive and substring-based so `"M"` matches `"S/M"` and `"M/L"`. `None` skips the size filter entirely.
- `max_price` (float | None): Inclusive price ceiling, e.g. `30.0`. Listings with `price > max_price` are excluded. `None` skips the price filter.

**What it returns:**
A `list[dict]` of full listing dicts, sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str). Returns an empty list `[]` when nothing matches — it never raises.

**What happens if it fails or returns nothing:**
Returns `[]` rather than raising. The planning loop detects the empty list, stores a user-facing error message in session state ("No matches for '<description>' under $<max_price> in size <size> — try raising your budget, dropping a keyword, or removing the size filter."), and returns early **without** calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Takes the chosen thrifted item and the user's wardrobe and asks the LLM (Groq) to propose 1–2 complete outfits. When the wardrobe has items, it pairs the new piece with specific named pieces the user already owns; when the wardrobe is empty, it falls back to general styling advice for the item.

**Input parameters:**
- `new_item` (dict): The selected listing dict from `search_listings` (the top result). Its `title`, `category`, `colors`, and `style_tags` are formatted into the prompt so the LLM knows what it's styling.
- `wardrobe` (dict): A wardrobe dict shaped `{"items": [...]}`, where each item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. May be `{"items": []}` — this is handled gracefully, not as an error.

**What it returns:**
A non-empty `str` of natural-language styling advice (a few sentences). If `wardrobe["items"]` is non-empty, the text names real wardrobe pieces (e.g. "your baggy dark-wash jeans and chunky white sneakers"). If empty, it returns general advice about what pairs well and what vibe the piece suits.

**What happens if it fails or returns nothing:**
The empty-wardrobe case is not a failure — it returns general advice. If the LLM call itself errors (network/API), the tool returns a short fallback styling string rather than raising, so the loop can still proceed to `create_fit_card`. The function never returns an empty string.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, casual, shareable caption (Instagram/TikTok OOTD style) for the thrifted find and its styled outfit, using the LLM at a higher temperature so different inputs produce different captions.

**Input parameters:**
- `outfit` (str): The styling text returned by `suggest_outfit`. Gives the caption its outfit-specific flavor.
- `new_item` (dict): The selected listing dict. Its `title`, `price`, and `platform` are woven into the caption naturally (once each).

**What it returns:**
A 2–4 sentence `str` suitable as a social caption — casual and authentic, mentioning the item name, price, and platform once each, and capturing the outfit vibe in specific terms.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, the tool returns a descriptive error string (e.g. "Can't make a fit card without an outfit suggestion.") instead of raising. If the LLM call errors, it returns a simple fallback caption built from the item's title/price/platform so the user still gets something usable.

---

### Additional Tools (if any)

None — the agent uses exactly the three required tools.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop is a fixed three-step pipeline with an early-exit error branch. It does not loop indefinitely — it runs each stage once, in order, gated by the result of the previous stage.

1. **Parse the query.** Extract `description` (keywords), `size` (or `None`), and `max_price` (or `None`) from the user's natural-language input, and store them in `session["parsed"]`. **Parsing is done with regex, not an LLM** — the targets are simple bounded patterns (a "under $N"/"$N" price phrase and a "size X" phrase), so a deterministic parser is faster, free, and easy to unit-test. Filler words ("looking for a", etc.) are stripped from the description, and a stopword list keeps them out of relevance scoring.
2. **Call `search_listings(description, size, max_price)`.**
   - **If `results == []`:** set `session["error"]` to a specific message telling the user what to loosen, and `return session` immediately. Do **not** call `suggest_outfit` or `create_fit_card`.
   - **If `results` is non-empty:** set `session["search_results"] = results` and `session["selected_item"] = results[0]` (top relevance match), then continue.
3. **Call `suggest_outfit(selected_item, wardrobe)`.** `wardrobe` comes from session (example or empty wardrobe). Store the returned string as `session["outfit_suggestion"]`. This step always produces a non-empty string (empty wardrobe → general advice), so the loop always proceeds.
4. **Call `create_fit_card(outfit_suggestion, selected_item)`.** Store the result as `session["fit_card"]`.
5. **Return `session`** containing `selected_item`, `outfit_suggestion`, and `fit_card` (or `error` if it exited at step 2).

**How it knows it's done:** the pipeline is finished when `fit_card` is set (success) or when `error` is set (early exit). There is exactly one decision point — the empty-vs-non-empty check after `search_listings`.

---

## State Management

**How does information from one tool get passed to the next?**

State lives in a single `session` dict that the planning loop owns and threads through the pipeline. Each tool reads what it needs from `session` and writes its output back, so the next tool can pick it up:

| Key | Set by | Read by |
|-----|--------|---------|
| `query` / `description` / `size` / `max_price` | query parse step | `search_listings` |
| `wardrobe` | session init (`get_example_wardrobe()` or `get_empty_wardrobe()`) | `suggest_outfit` |
| `search_results` | `search_listings` | planning loop (empty check) |
| `selected_item` | planning loop (`= search_results[0]`) | `suggest_outfit`, `create_fit_card` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | final output to user |
| `error` | planning loop (on empty results) | final output to user |

The key handoffs: `search_listings` → `selected_item` → `suggest_outfit` → `outfit_suggestion` → `create_fit_card`. No tool calls another tool directly; the loop is the only thing that reads and writes `session`, which keeps data flow explicit and testable.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Stop the pipeline and tell the user exactly what blocked the search and what to change: "No matches for '<description>' under $<max_price> in size <size>. Try raising your budget, removing the size filter, or using broader keywords (e.g. 'graphic tee' instead of 'vintage band tee')." Does not call the other two tools. |
| suggest_outfit | Wardrobe is empty | Don't error — switch to general styling advice: "Your closet's empty, so here's how I'd style this on its own: pair it with <complementary categories/colors> for a <vibe> look." The pipeline continues to create_fit_card with this advice. |
| create_fit_card | Outfit input is missing or incomplete | If `outfit` is empty/whitespace, return a clear message instead of a caption: "I need an outfit suggestion before I can write a fit card — let's style the item first." If the LLM call fails, return a simple fallback caption built from the item's title, price, and platform so the user still gets something postable. |

---

## Architecture

```
User query: "vintage graphic tee under $30, I wear baggy jeans + chunky sneakers"
    │  (parse → description, size, max_price)
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PLANNING LOOP  (owns + threads the `session` dict)                        │
│                                                                           │
│   session = { query, description, size, max_price, wardrobe }            │
│                                                                           │
│   ├─► search_listings(description, size, max_price)                       │
│   │        │                                                              │
│   │        │  results == []                                              │
│   │        ├──► session["error"] = "No matches… try X" ──► return session │ ◄─ ERROR BRANCH
│   │        │                                              (stops here;     │   (terminates early)
│   │        │                                               tools 2 & 3     │
│   │        │                                               NOT called)     │
│   │        │  results == [item, ...]                                      │
│   │        ▼                                                              │
│   │   session["search_results"] = results                                │
│   │   session["selected_item"]  = results[0]                             │
│   │        │                                                              │
│   │        │  (selected_item, wardrobe)                                  │
│   ├─► suggest_outfit(selected_item, wardrobe) ──► LLM (Groq)             │
│   │        │   empty wardrobe → general advice                            │
│   │        ▼                                                              │
│   │   session["outfit_suggestion"] = "..."                              │
│   │        │                                                              │
│   │        │  (outfit_suggestion, selected_item)                        │
│   └─► create_fit_card(outfit_suggestion, selected_item) ──► LLM (Groq)   │
│            │                                                              │
│            ▼                                                              │
│        session["fit_card"] = "..."                                       │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
   Return session ──► User sees: selected listing + outfit suggestion + fit card
                      (or, on the error branch, just the error message)
```

Data flows one direction through `session`: each tool reads its inputs from `session` and writes its output back, and the planning loop is the only component that reads/writes state or decides what runs next. The single branch point is the empty-results check after `search_listings`, which is where the error path terminates early.

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll use **Claude (Claude Code)** for all three tools, one at a time.

- **`search_listings`:** I'll give Claude the *Tool 1* block from this planning.md (the three params with types, the scored-and-sorted return contract, and the empty-list failure mode) plus the `load_listings()` docstring from `utils/data_loader.py`. I expect it to produce a function that (1) calls `load_listings()`, (2) filters by `max_price` and case-insensitive substring `size`, (3) scores by keyword overlap across title/description/style_tags, (4) drops zero-score items, (5) sorts descending. **Verify before trusting:** read the code to confirm all three params are actually applied and `[]` is returned (not an exception) when nothing matches, then test 3 queries — "vintage graphic tee" `max_price=30` (expect lst_006/033/002), a `size="M"` query, and an impossible query like `max_price=5` (expect `[]`).
- **`suggest_outfit`:** I'll give Claude the *Tool 2* block plus the wardrobe schema from `data/wardrobe_schema.json` and the `_get_groq_client()` helper already in `tools.py`. I expect a function that branches on `wardrobe["items"]` empty vs non-empty and calls the LLM with the item + wardrobe formatted into the prompt. **Verify:** test once with `get_example_wardrobe()` (output must name real pieces like the baggy jeans / chunky sneakers) and once with `get_empty_wardrobe()` (must return general advice, never empty/crash).
- **`create_fit_card`:** I'll give Claude the *Tool 3* block (style guidelines + empty-outfit guard + higher temperature). I expect a function that guards whitespace-only `outfit`, builds a caption prompt, and returns 2–4 sentences mentioning name/price/platform. **Verify:** run it twice on the same item to confirm captions differ, check name/price/platform each appear once, and pass `outfit=""` to confirm it returns the error string, not a crash.

**Milestone 4 — Planning loop and state management:**

I'll use **Claude** and give it the *Planning Loop*, *State Management*, *Error Handling*, and *Architecture* sections together (the ASCII diagram is the key artifact — it shows the branch point and error exit). I expect it to produce an `agent.py` planning function that initializes `session`, calls the three tools in order, performs the empty-results early return, and threads outputs through `session` exactly as the state table specifies. **Verify before trusting:** trace the generated code against the diagram — confirm it returns early on `[]` *without* calling tools 2/3, confirm `selected_item = results[0]`, and confirm each tool reads its input from the prior tool's session key. Then run the full happy-path query from *A Complete Interaction* and the `max_price=5` error-path query, checking the returned session matches the expected keys in each case.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**What FitFindr does (in my own words):** FitFindr is a thrift-shopping assistant that takes a user's natural-language request, searches a mock secondhand-listings dataset for items matching their description, size, and budget, then styles the best find against the pieces already in their wardrobe and writes a shareable caption for it. The user's request triggers `search_listings`; a non-empty search result triggers `suggest_outfit` (on the top match plus the user's wardrobe); and a successful outfit suggestion triggers `create_fit_card`. If `search_listings` returns nothing, FitFindr stops, tells the user what to loosen (price, size, or keywords), and never calls `suggest_outfit` with empty input; if the wardrobe is empty, `suggest_outfit` falls back to general styling advice instead of failing; and if the outfit text is missing, `create_fit_card` returns an error message rather than raising.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the request into search parameters and calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. (No size was stated, so the size filter is skipped.) This returns the matching listings sorted by relevance: `lst_006` "Graphic Tee — 2003 Tour Bootleg Style" ($24, depop), `lst_033` "Vintage Band Tee — Faded Grey" ($19, depop), and `lst_002` "Y2K Baby Tee — Butterfly Print" ($18, depop). The agent picks the top result, `lst_006`.

**Step 2:**
Because Step 1 returned at least one listing, the agent calls `suggest_outfit(new_item=<lst_006>, wardrobe=<example wardrobe>)`. The wardrobe (`get_example_wardrobe()`) contains the user's baggy straight-leg jeans (`w_001`) and chunky white sneakers (`w_007`), so the tool returns a specific suggestion, e.g. "Wear the bootleg graphic tee with your baggy dark-wash jeans and chunky white sneakers for an easy 90s streetwear look — tuck the front hem and add the black crossbody bag."

**Step 3:**
With a non-empty outfit string in hand, the agent calls `create_fit_card(outfit=<suggestion>, new_item=<lst_006>)`, which returns a casual caption, e.g. "found this faded 2003 tour tee on depop for $24 and it's already my favorite 🖤 styled it with my baggy jeans + chunky sneakers, full 90s mode."

**Final output to user:**
The user sees the chosen listing (title, price, platform, condition), the styling suggestion that uses pieces from their own wardrobe, and the ready-to-post fit card caption — all in one response.

**Error path:** If the query had been "vintage graphic tee under $10," `search_listings` would return an empty list. The agent would stop after Step 1 and reply with something like "No vintage graphic tees under $10 right now — try raising your budget to ~$20 or dropping the 'vintage' keyword," without ever calling `suggest_outfit` or `create_fit_card`.
