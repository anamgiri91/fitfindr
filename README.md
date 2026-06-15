# FitFindr

An AI-powered thrift shopping agent that takes a natural language query, finds matching secondhand listings, scores the buy decision, suggests complete outfits, and generates a shareable fit card — all in a single interaction.

---

## Tool Inventory

FitFindr uses six tools. All three required tools plus three supporting tools are wired through a single planning loop.

---

### `search_listings(description, size, max_price)`

**Purpose:** Searches `data/listings.json` for items matching the user's query. Filters by size and price ceiling, then ranks remaining items by keyword overlap with the description.

**Inputs:**
- `description` (str) — keywords describing the item (e.g. `"vintage graphic tee"`)
- `size` (str | None) — size string to filter by, case-insensitive; `None` skips size filtering
- `max_price` (float | None) — maximum price inclusive; `None` skips price filtering

**Returns:** `list[dict]` — a list of matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns an empty list if nothing matches — never raises an exception.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given the item the user is considering and their existing wardrobe, generates 1–2 complete outfit combinations by matching style tags and complementary colors. Falls back to general styling advice when the wardrobe is empty.

**Inputs:**
- `new_item` (dict) — a single listing dict returned by `search_listings`
- `wardrobe` (dict) — the user's wardrobe with an `items` key containing a list of wardrobe item dicts; may be empty

**Returns:** `str` — a non-empty string with 1–2 outfit suggestions. If the wardrobe has items, suggestions name specific wardrobe pieces and explain why they work together. If the wardrobe is empty, the string gives general styling advice for the item's vibe and occasion.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Takes the outfit suggestion string and the listing dict and generates a 2–4 sentence Instagram/TikTok-style caption that sounds like a real person posting an OOTD — not a product listing.

**Inputs:**
- `outfit` (str) — the outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict) — the listing dict for the thrifted item being featured

**Returns:** `str` — a casual, shareable caption that mentions the item name, price, and platform once each and captures the outfit's specific vibe. If `outfit` is empty or missing, returns a descriptive error string instead of raising an exception.

---

### `score_listing(item, wardrobe, style_profile)`

**Purpose:** Scores a listing 0–10 based on how much value it adds to the wardrobe. Evaluates style tag overlap, category redundancy, item condition, and style profile preferences to give a buy confidence verdict.

**Inputs:**
- `item` (dict) — a single listing dict from `search_listings`
- `wardrobe` (dict) — the user's current wardrobe with an `items` key
- `style_profile` (dict | None) — optional user preferences: `preferred_colors`, `style_tags`, `avoided_categories`

**Returns:** `dict` with:
- `score` (float) — buy confidence from 0–10
- `reasons` (list[str]) — plain-English strings explaining what raised or lowered the score
- `verdict` (str) — one of `"strong buy"`, `"maybe"`, or `"pass"`
- `low_confidence` (bool) — `True` if the wardrobe was empty and the score is a partial estimate

---

### `estimate_price_fairness(item, condition_weight)`

**Purpose:** Scans the dataset for comparable listings (same category, at least one shared style tag) and estimates whether the item's price is a deal, fair, or overpriced relative to real comparables.

**Inputs:**
- `item` (dict) — a single listing dict from `search_listings`
- `condition_weight` (float) — 0–1 value controlling how much condition affects the estimate; defaults to `0.5`

**Returns:** `dict` with:
- `verdict` (str) — one of `"great deal"`, `"fair price"`, `"overpriced"`, or `"not enough data"`
- `average_comparable_price` (float) — mean price of comparable items used in the estimate
- `comparables_found` (int) — number of matching items used
- `reasoning` (str) — plain-English explanation (e.g. `"4 similar tops average $31 — this is priced at $22. Verdict: great deal."`)

---

### `explain_style_gap(wardrobe)`

**Purpose:** Analyzes the user's wardrobe and identifies what's missing — by category, versatility tags, and color variety — then produces a ready-made search query the agent can pass directly into `search_listings`.

**Inputs:**
- `wardrobe` (dict) — the user's current wardrobe with an `items` key; handles empty wardrobes

**Returns:** `dict` with:
- `gaps` (list[str]) — plain-English descriptions of what's missing or underrepresented
- `category_counts` (dict) — maps each expected category to how many items the user owns
- `suggested_search` (str) — a ready-made description string to pass into `search_listings`

---

## Planning Loop

The agent follows a conditional sequence — each tool's output determines whether the next tool runs, is skipped, or triggers a retry. The loop does not call all tools unconditionally.

**Step 1 — Does the user have a specific item in mind?**
- Yes → skip `explain_style_gap`, call `search_listings` directly
- No → call `explain_style_gap` on the current wardrobe; use `suggested_search` from the result to populate the `search_listings` call

**Step 2 — `search_listings`**
- Returns results → save top result to `session["selected_item"]`, proceed to Step 3
- Returns empty list → agent tells the user specifically what caused the miss (size unavailable, over budget, or no keyword overlap) and asks them to adjust; loop restarts at Step 2

**Step 3 — `estimate_price_fairness` and `score_listing`**
- Both run on `selected_item`; the price verdict feeds into `score_listing` as a signal
- `verdict` is `"strong buy"` or `"maybe"` → proceed to Step 4
- `verdict` is `"pass"` → agent surfaces the specific reasons (e.g. redundancy, poor condition), offers a new search; loop restarts at Step 2

**Step 4 — `suggest_outfit`**
- Returns outfit string → save to `session["outfits"]`, proceed to Step 5
- Wardrobe is empty → tool returns general styling advice; agent proceeds to Step 5 and notes the wardrobe is empty

**Step 5 — `create_fit_card`**
- LLM generates caption → save to `session["fit_card"]`, present to user
- `outfit` string is empty → tool returns a descriptive error string; agent surfaces it rather than crashing

The agent knows it's done when `create_fit_card` returns a result and the user has been shown the fit card. It then asks if they'd like to search again or refine the current item.

---

## State Management

The agent maintains a single `session` dict that accumulates results as tools run. No tool ever re-asks the user for something a previous tool already returned.

```python
session = {
    "wardrobe":       None,   # loaded once at session start
    "style_profile":  None,   # loaded once at session start
    "search_results": [],     # populated by search_listings
    "selected_item":  None,   # top result, saved after search_listings
    "price_verdict":  None,   # populated by estimate_price_fairness
    "score_result":   None,   # populated by score_listing
    "outfits":        [],     # populated by suggest_outfit
    "fit_card":       None,   # populated by create_fit_card
    "error":          None,   # set if any tool fails unrecoverably
}
```

**How state flows between tools:**

- `explain_style_gap` reads `wardrobe`; its `suggested_search` output is passed directly as the `description` arg to `search_listings`
- `search_listings` writes its results list to `search_results`; the agent picks `results[0]` and writes it to `selected_item`
- `estimate_price_fairness` reads `selected_item`; writes its full result dict to `price_verdict`
- `score_listing` reads `selected_item`, `wardrobe`, `style_profile`, and `price_verdict`; writes its result to `score_result`
- `suggest_outfit` reads `selected_item` and `wardrobe`; writes the outfit string list to `outfits`
- `create_fit_card` reads `outfits[0]` and `selected_item`; writes the caption to `fit_card`

The item returned by `search_listings` is the exact same dict passed into `suggest_outfit` and `create_fit_card` — the user never re-enters it. If a `"pass"` verdict is returned, the agent clears only `search_results`, `selected_item`, `price_verdict`, `score_result`, `outfits`, and `fit_card` and restarts from Step 2 with the rest of the session intact.

---

## Error Handling

### Per-tool failure modes

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | Returns empty list (size unavailable, over budget, or no keyword overlap) | Agent tells the user exactly which filter caused the miss and asks them to adjust size, price, or keywords. Does not proceed to scoring. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"]` is `[]`) | Tool returns general styling advice rather than crashing or returning an empty string. Agent notes the wardrobe is empty and proceeds to `create_fit_card`. |
| `create_fit_card` | `outfit` string is empty or `None` | Tool returns the string `"Couldn't generate a caption — no outfit suggestion was provided."` Agent surfaces this message in the fit card panel rather than raising an exception. |
| `score_listing` | Wardrobe is empty or `style_profile` is `None` | Tool scores on available fields only and sets `low_confidence: True`. Agent shows the score with a note that it's a partial estimate. |
| `estimate_price_fairness` | Fewer than 2 comparable items found | Returns `verdict: "not enough data"` with a plain-English explanation. Agent shows this honestly rather than omitting the price panel. |
| `explain_style_gap` | Wardrobe is empty | Returns a default starter gap list with sensible starter recommendations. Agent uses `suggested_search` from the result to begin searching without asking the user anything. |

### Concrete example from testing

**Deliberately triggered failure — `create_fit_card` with empty outfit string:**

```
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```

Output:
```
Couldn't generate a caption — no outfit suggestion was provided.
```

The guard `if not outfit or not outfit.strip(): return "..."` catches both empty strings and whitespace-only strings before the Groq API is ever called, so no network request is made and no exception propagates.

**Deliberately triggered exception (before fix) — `create_fit_card` with `None`:**

```
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card(None, results[0]))
"
```

Output:
```
TypeError: create_fit_card requires a non-empty outfit string.
```

This was the failure documented in the demo. The fix was updating the guard to `if outfit is None or not outfit.strip()` so `None` is caught explicitly before `.strip()` is called.

**No-results path from agent run:**

```
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
[]
```

The full agent run with this query produced:
```
No listings found for "designer ballgown" in size XXS under $5 — try broadening your size, price, or keywords.
```

The agent identified the specific constraint combination that caused the miss rather than returning a generic "no results" message.

---

## Complete Interaction Walkthrough

**User query:** `"I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers."`

**Step 1 — Planning check:** User named a specific item, so `explain_style_gap` is skipped. Agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`. Dataset returns matching listings. Top result — Y2K Baby Tee, $18, Depop — is saved to `session["selected_item"]`.

**Step 2 — Price check:** Agent calls `estimate_price_fairness(item=selected_item)`. Finds comparable tops averaging $31. Returns `verdict: "great deal"`, saved to `session["price_verdict"]`.

**Step 3 — Score:** Agent calls `score_listing(item=selected_item, wardrobe=wardrobe, style_profile=None)`. Reads `price_verdict` from session. Finds 3 wardrobe items with overlapping style tags (`"y2k"`, `"vintage"`). Returns `score: 7.5`, `verdict: "maybe"`. Saved to `session["score_result"]`.

**Step 4 — Outfit:** Verdict is `"maybe"` so agent proceeds. Calls `suggest_outfit(new_item=selected_item, wardrobe=wardrobe)`. Generates two complete outfit combinations using the example wardrobe. Saved to `session["outfits"]`.

**Step 5 — Fit card:** Agent calls `create_fit_card(outfit=outfits[0], new_item=selected_item)`. LLM generates a casual caption mentioning the item name, $18 price, and Depop platform. Saved to `session["fit_card"]` and shown to the user.

At every step, the item dict flows forward through session state — the user never re-enters it.

---

## Spec Reflection

**One way the spec helped:** The explicit requirement that `search_listings` return an empty list rather than raise an exception on no results shaped the entire error handling architecture. Because the tool contract guaranteed a safe return value, the planning loop could check `if not results` cleanly rather than wrapping every tool call in try/except. That single constraint kept the agent code readable.

**One divergence and why:** The planning.md spec described `create_fit_card` returning a dict with `caption`, `tags`, and `title` fields. In practice, the Gradio UI needed a single string it could drop directly into a text panel — so the implementation was simplified to return just the caption string. Generating structured JSON from the LLM and immediately discarding the tags and title added latency and parsing complexity for no user-visible benefit. The spec was written before the UI was designed; once the output destination was clear, the simpler interface was the right call.

---

## AI Usage

### Instance 1 — Implementing `search_listings`

**What I gave the AI:** The Tool 1 spec from `planning.md` (inputs with types, return value description, failure mode), plus the relevant section of the architecture diagram showing that `search_listings` writes to `session["search_results"]` and that an empty result must not raise an exception.

**What it produced:** A working implementation that filtered by size and price and returned a sorted list. It initially used substring matching on size (e.g. `"M" in "S/M"`) which caused decade strings like `"50s"` and `"1990s"` to match size `"S"`. It also set `min_score = 1` for all queries.

**What I changed:** Added a full-word isolation requirement for bare size tokens using a regex boundary check, and raised `min_score` to 2 for multi-word queries to reduce noise results. Both changes were verified by running the three test queries from the AI Tool Plan before moving on.

---

### Instance 2 — Implementing the planning loop in `agent.py`

**What I gave the AI:** The full architecture Mermaid diagram from `planning.md`, the state management section showing the session dict and what each tool reads and writes, and the error handling table. I asked it to implement `run_agent()` as a single function that orchestrates tool calls conditionally based on each tool's output.

**What it produced:** A working planning loop that handled the happy path correctly. However, it called `suggest_outfit` unconditionally even when `score_listing` returned a `"pass"` verdict — the conditional branch was missing. It also did not populate `session["error"]` on the no-results path; it raised a Python exception instead.

**What I changed:** Added the `if score_result["verdict"] == "pass": return session` early exit before `suggest_outfit` is called. Replaced the exception on empty results with `session["error"] = "No listings found..."` and a clean return, matching the error handling contract described in the spec. Both changes were tested against the no-results path and the pass-verdict path before wiring the agent into `app.py`.