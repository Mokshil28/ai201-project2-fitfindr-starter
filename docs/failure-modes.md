# FitFindr — Triggered Failure Modes (Milestone 5)

Each tool's failure mode was triggered deliberately from the terminal and
confirmed to return a specific, informative response — never a Python exception
and never an empty value.

## 1. `search_listings` returns no results

```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```
Output:
```
[]
```
Returns an empty list — no exception.

Run through the full agent on the same impossible query:
```bash
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; print(run_agent('designer ballgown size XXS under \$5', get_example_wardrobe())['error'])"
```
Output:
```
No matches for 'designer ballgown' under $5 in size XXS. Try raising your
budget, removing the size filter, or using broader keywords.
```
The agent explains *what* failed and *what to try*, and never calls
`suggest_outfit`/`create_fit_card` (both `selected_item` and `fit_card` stay
`None`).

## 2. `suggest_outfit` with an empty wardrobe

```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```
Output (example):
```
This awesome vintage band tee is perfect for adding a grunge touch to your
wardrobe - pair it with distressed denim jeans and combat boots for a laid-back,
streetwear-inspired look. ...
```
Returns useful general styling advice instead of crashing or returning an empty
string.

## 3. `create_fit_card` with an empty outfit

```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```
Output:
```
I need an outfit suggestion before I can write a fit card — let's style the item first.
```
Returns a descriptive error message string — not a Python exception.

## Automated coverage

These failure modes are also covered by `tests/test_tools.py`
(`test_search_empty_results`, `test_suggest_outfit_empty_wardrobe_does_not_crash`,
`test_create_fit_card_empty_outfit_returns_error_message`). Run with:
```bash
python -m pytest tests/
```
