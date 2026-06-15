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
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

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
