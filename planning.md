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
This function searches listings form listing.json and returns the matching items by filtering description keywords, size, and max_price against the listings dataset.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The description of the item that is being searched
- `size` (str): The size of the product(e.g. : W30 L30)
- `max_price` (float): The maximum price of the product

**What it returns:**
It returns a list of listing dicts, each with fields like title, price, platform, condition, etc.

**What happens if it fails or returns nothing:**
If it fails, it returns an empty list with a message explaining why (no size match, over budget, no keyword overlap), and the agent either retries with loosened constraints or asks the user to adjust their search.

---

### Tool 2: suggest_outfit

**What it does:**
When we give it a item and the user's warddrobe history it recommends the complete outfit for the user. It matches items by overlapping style_tags and complementary colors, so suggestions feel intentional rather than random. 
||.   

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A single listing dict returned by search_listings, representing the item the user is considering buying
- `wardrobe` (dict): The user's current wardrobe with an items list, sourced from either get_example_wardrobe() or get_empty_wardrobe()

**What it returns:**
A list of outfit dicts, each containing:

items (list of str): the names of the wardrobe pieces that pair with the new item
reasoning (str): a short plain-English explanation of why these pieces work together
completeness (str): one of "complete" or "partial" — flagging whether the outfit covers all key categories (top, bottom, shoes) or is missing something

**What happens if it fails or returns nothing:**
If the wardrobe is empty or has too few items to build a full outfit, the tool returns a "partial" outfit with whatever is available and notes which categories are missing. It never crashes or returns silently . The agent uses the completeness flag to tell the user what they'd still need to complete the look.

---

### Tool 3: create_fit_card

**What it does:**
Takes a complete outfit and the new item being considered and generates a short, shareable caption-style description — the kind of thing someone would post alongside an outfit photo. It uses the LLM to produce something that sounds human and styled rather than like a product listing, and produces a different result for different outfit combinations.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (dict): A single outfit dict returned by suggest_outfit, containing the list of paired items and the reasoning behind the combination
- `new_item` (string) : The listing dict for the item the user is considering, used to anchor the tone and focus of the caption

**What it returns:**
A dict with:

caption (str): a 2–3 sentence Instagram-style outfit description that highlights the vibe, key pieces, and how the new item ties the look together
tags (list of str): 3–5 relevant hashtags derived from the outfit's style_tags and colors
title (str): a short punchy outfit name (e.g. "Sunday Market Fit" or "Quiet Luxury, Loud Savings")


**What happens if it fails or returns nothing:**
If the LLM returns an unusable or empty response, the tool falls back to a templated caption built directly from the outfit's style_tags, colors, and item names — so the user always gets something shareable even if the generated version fails. The agent flags to the user that the caption was auto-generated rather than styled.

---

### Additional Tools (if any)

4. score_listing
**What it does:**
Given a listing the user is considering, their existing wardrobe, and their style preferences, this tool produces a 0–10 buy score with plain-English reasoning. It goes beyond simply checking if an item matches outfits — it evaluates whether the purchase actually adds value to the wardrobe, flagging redundancy, condition concerns, and price fairness so the agent can act as a shopping advisor rather than just a search engine.

**Input parameters:**

item (dict): A single listing dict returned by search_listings, representing the item being evaluated
wardrobe (dict): The user's current wardrobe with an items list, sourced from get_example_wardrobe() or get_empty_wardrobe()
style_profile (dict): User preferences including preferred colors, styles, and categories they're actively building toward

**What it returns:**
A dict with:

score (float): a value from 0–10 representing overall buy confidence
reasons (list of str): short plain-English strings explaining what raised or lowered the score
verdict (str): one of "strong buy", "maybe", or "pass"

**What happens if it fails or returns nothing:**
If wardrobe is empty, the tool scores using style_profile and item fields alone and attaches a low-confidence flag to the result. If style_profile is missing, preference scoring is skipped without crashing. A verdict is always returned — the agent uses a "pass" verdict to skip outfit generation and offer a new search instead.

Tool 5: estimate_price_fairness
**What it does:**
Given a listing the user is considering, this tool scans the rest of the dataset for comparable items and estimates whether the price is fair, too high, or a steal. It gives the user concrete context — not just a gut feeling — by anchoring the item's price against real comparables filtered by category, condition, and style similarity.

**Input parameters:**
item (dict): A single listing dict returned by search_listings, representing the item being evaluated
condition_weight (float, optional): A 0–1 value controlling how much condition affects the fairness estimate; defaults to 0.5 if not provided

**What it returns:**
A dict with:

verdict (str): one of "great deal", "fair price", or "overpriced"
average_comparable_price (float): the mean price of similar items found in the dataset
comparables_found (int): how many matching items were used to calculate the estimate
reasoning (str): a plain-English explanation like "3 similar items in good condition average $34 — this is priced at $22"

**What happens if it fails or returns nothing:**
If fewer than 2 comparable items are found, the tool returns a "not enough data" verdict with a note explaining why — too niche a category, no condition matches, etc. The agent surfaces this to the user honestly rather than producing a misleading estimate from a single data point.
Planning loop role:
Runs alongside score_listing immediately after search_listings — both take the found item as input. The verdict feeds into score_listing as a pricing signal, so a "great deal" can boost the buy score and "overpriced" can lower it, making the two tools work together rather than independently.

Tool 6: explain_style_gap

**What it does:**
Analyzes the user's current wardrobe and identifies what's missing — by category count, versatility tags, and color variety. Produces a ready-made search query the agent can pass directly into search_listings when the user doesn't know what they're looking for.

**Input parameters:**
- `wardrobe` (dict): The user's current wardrobe with an `items` key; handles empty wardrobes without crashing

**What it returns:**
A dict with:
- `gaps` (list of str): plain-English descriptions of what's missing or underrepresented (e.g. "No outerwear listed — this is a key missing category")
- `category_counts` (dict): maps each expected category to how many items the user currently owns
- `suggested_search` (str): a ready-made description string to pass directly into search_listings (e.g. "versatile outerwear")

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the tool returns a default starter gap list with sensible recommendations rather than crashing. The agent uses `suggested_search` from the result to begin the search flow without needing any input from the user.

**Planning loop role:**
Only called when `knows_what_they_want=False` — the "No" branch in the architecture diagram. Its `suggested_search` output replaces the description in the parsed query before search_listings is called, so the agent can still run a full interaction even when the user has no specific item in mind.
---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent follows a conditional sequence — each tool's output determines whether the next tool runs, is skipped, or triggers a fallback. The loop works like this:
Step 1 — Does the user have a specific item in mind?

Yes → go to Step 2
No → run explain_style_gap first, use suggested_search output to populate search_listings, then go to Step 2

Step 2 — Run search_listings

Returns results → go to Step 3
Returns empty → agent informs the user why (size, price, or keyword issue) and asks them to adjust; loop restarts at Step 2

Step 3 — Run estimate_price_fairness and score_listing on the top result

estimate_price_fairness verdict feeds into score_listing as a pricing signal
score_listing verdict is "strong buy" or "maybe" → go to Step 4
score_listing verdict is "pass" → agent surfaces the reasons, offers to search again; loop restarts at Step 2

Step 4 — Run suggest_outfit

Returns "complete" outfits → go to Step 5
Returns only "partial" outfits → agent notes what categories are missing, proceeds to Step 5 anyway

Step 5 — Run create_fit_card

Generates caption, tags, and title → agent presents the full fit card to the user
LLM fails → falls back to templated caption; agent flags it as auto-generated

The agent knows it's done when create_fit_card returns a result and the user has been shown the final fit card. At that point the agent asks if they'd like to search for another item or refine the current one.

---

## State Management

**How does information from one tool get passed to the next?**
The agent maintains a single session state dict that gets built up and passed forward as tools run. No tool ever asks the user to re-enter something that was already returned by a previous tool call.
The session state looks like this:

session = {
    "wardrobe": None,        # loaded once at session start
    "style_profile": None,   # loaded once at session start
    "search_results": [],    # populated by search_listings
    "selected_item": None,   # the item the user decides to evaluate
    "price_verdict": None,   # populated by estimate_price_fairness
    "score_result": None,    # populated by score_listing
    "outfits": [],           # populated by suggest_outfit
    "fit_card": None,        # populated by create_fit_card
}

How each tool reads and writes state:

explain_style_gap — reads wardrobe; writes suggested_search directly into the next search_listings call
search_listings — writes its results list to search_results; the agent picks the top result and writes it to selected_item
estimate_price_fairness — reads selected_item; writes its verdict to price_verdict
score_listing — reads selected_item, wardrobe, style_profile, and price_verdict; writes its full result to score_result
suggest_outfit — reads selected_item and wardrobe; writes its outfit list to outfits
create_fit_card — reads outfits[0] and selected_item; writes the final card to fit_card

Nothing is re-requested from the user unless a tool returns empty or a verdict of "pass" — in which case the agent clears search_results and selected_item and restarts from search_listings with the session otherwise intact.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query |  queryReturns an empty list with a message specifying why (size unavailable, over budget, no keyword match); agent relays the specific reason to the user and either retries with loosened constraints or asks them to adjust their search |
| suggest_outfit | Wardrobe is empty | Returns a "partial" outfit with whatever is available and flags which categories are missing; agent tells the user what they'd still need to complete the look and proceeds anyway |
| create_fit_card | Outfit input is missing or incomplete | Falls back to a templated caption built from the outfit's style_tags, colors, and item names; agent flags to the user that the caption was auto-generated rather than styled |
| score_listing | wardrobe is empty or style_profile is missing | Scores on available fields only and attaches a low-confidence flag to the result; agent surfaces the flag so the user knows the score is a partial estimate|
| estimate_price_fairness | Fewer than 2 comparable items found in the dataset | Returns a "not enough data" verdict with a plain-English explanation of why comparables were scarce; agent presents this honestly rather than producing a misleading estimate |
|explain_style_gap| Wardrobe is empty | Returns a default starter gap list with sensible recommendations; agent uses this to begin the search flow without needing any input from the user |

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

     ```mermaid
flowchart TD
    A([User Input]) --> B{Does user know\nwhat they want?}

    B -- No --> C[explain_style_gap]
    C --> D[suggested_search\npopulates search query]
    D --> E[search_listings]

    B -- Yes --> E

    E -- No results --> F[Agent explains why\nask user to adjust]
    F --> E

    E -- Results found --> G[selected_item\nsaved to session]

    G --> H[estimate_price_fairness]
    G --> I[score_listing]
    H -- price_verdict --> I

    I -- verdict: pass --> J[Agent surfaces reasons\noffers new search]
    J --> E

    I -- verdict: strong buy\nor maybe --> K[suggest_outfit]

    K -- partial outfits --> L[Agent flags\nmissing categories]
    L --> M[create_fit_card]
    K -- complete outfits --> M

    M -- LLM fails --> N[Templated fallback caption\nagent flags auto-generated]
    M -- Success --> O([Fit card shown to user])
    N --> O

    O --> P{Search again\nor refine?}
    P -- Yes --> E
    P -- No --> Q[Save session to\nprofile.json]
    Q --> R([Session ends])

    subgraph Session State
        S[(wardrobe\nstyle_profile\nsearch_results\nselected_item\nprice_verdict\nscore_result\noutfits\nfit_card)]
    end

    E & H & I & K & M <-.reads/writes.-> S
```
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

I'll use Claude for each tool, one at a time. For each tool I'll paste in: the tool's spec from this planning.md (inputs, return value, failure mode) plus the relevant section of the architecture diagram showing what the tool reads and writes to session state. I'll ask it to implement the function using load_listings() and load_wardrobe_schema() from the data loader where relevant.
Verification steps before moving on:

search_listings — test against 3 queries: one that returns results, one where size filters everything out, and one where max_price filters everything out. Confirm the failure message is specific in each case.
suggest_outfit — test against get_example_wardrobe() (should return complete outfits) and get_empty_wardrobe() (should return partial with missing categories flagged). Confirm it never crashes.
create_fit_card — run it 3 times on different outfit inputs and confirm each caption is distinct. Force an empty LLM response and confirm the fallback template kicks in.
score_listing — test with a redundant item (4th item in same category) and confirm score is penalized. Test with empty wardrobe and confirm low-confidence flag appears in output.
estimate_price_fairness — test with a common category that has many comparables, and with a niche item that has fewer than 2. Confirm "not enough data" verdict appears in the second case.

**Milestone 4 — Planning loop and state management:**
I'll use ChatGPT for the planning loop and state management. I'll give it: the full architecture diagram, the state management section of this planning.md showing the session dict and what each tool reads and writes, and the error handling table. I'll ask it to implement the planning loop as a single function that takes user input and orchestrates tool calls conditionally based on each tool's output.
Verification steps before moving on:

Run a full end-to-end session with a user who has a specific item in mind — confirm all 5 tools fire in the correct order and session state is populated at each step.
Run a session where search_listings returns empty — confirm the loop restarts correctly and doesn't proceed to score_listing.
Run a session where score_listing returns "pass" — confirm suggest_outfit and create_fit_card are skipped.
Check that profile.json is written at session end and reloaded correctly at the start of a second session without asking the user anything.
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent has a specific item in mind so it skips explain_style_gap and calls search_listings directly with description="vintage graphic tee", size="M" (inferred from profile), and max_price=30.0. The dataset returns 3 matching listings. The agent picks the top result — a $22 band tee in good condition from Depop — and saves it to session["selected_item"].
**Step 2:**
The agent calls estimate_price_fairness on the selected item. It finds 4 comparable graphic tees in the dataset averaging $31. It returns a verdict of "great deal" with reasoning: "4 similar items in good condition average $31 — this is priced at $22." The verdict is saved to session["price_verdict"].
**Step 3:**
The agent calls score_listing with the selected item, the user's wardrobe, and their style profile. It reads the "great deal" price verdict from session state and uses it as a positive signal. It finds 3 wardrobe items with overlapping style tags ("vintage", "streetwear") and no redundancy in the tops category. It returns a score of 8.2, verdict "strong buy", with reasons: "pairs with 3 wardrobe items", "fills a gap in tops", "priced well below comparable listings."
**Step 4:**
Verdict is "strong buy" so the agent proceeds and calls suggest_outfit with the selected item and the user's wardrobe. It finds 2 complete outfit combinations using overlapping style_tags and complementary colors. Both are saved to session["outfits"].
Step 5:
The agent calls create_fit_card with outfits[0] and the selected item. The LLM generates a caption, 4 hashtags, and an outfit title. The fit card is saved to session["fit_card"].
Step 6:
The agent writes the updated wardrobe and style profile to profile.json so preferences are remembered next session.