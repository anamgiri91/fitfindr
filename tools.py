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

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


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
    """
    listings = load_listings()

    # Step 2 — filter
    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        filtered.append(listing)

    # Step 3 — score (now includes style_tags and category)
    query_words = description.lower().split()
    scored = []
    for listing in filtered:
        listing_text = (
            listing["title"] + " " +
            listing["description"] + " " +
            " ".join(listing["style_tags"]) + " " +
            listing["category"]
        )
        listing_words = listing_text.lower().split()
        score = sum(1 for word in query_words if word in listing_words)
        scored.append((score, listing))

    # Step 4 — require at least 2 matching words for multi-word queries
    min_score = 2 if len(query_words) > 1 else 1
    scored = [(score, listing) for score, listing in scored if score >= min_score]

    # Step 5 — sort and return
    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for score, listing in scored]

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
    """
    client = Groq()

    item_description = (
        f"{new_item['title']} — {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])}"
    )

    # Step 1 — check if wardrobe is empty
    if not wardrobe["items"]:
        # Step 2 — general styling advice
        prompt = f"""A user is considering buying this secondhand item:
{item_description}

They don't have a wardrobe set up yet. Give them 1-2 suggestions for what kinds of 
pieces would pair well with this item and what vibe or occasion it suits best.
Keep it short, specific, and useful."""

    else:
        # Step 3 — specific outfit combinations
        wardrobe_lines = "\n".join(
            f"- {item['name']} ({item['category']}): {', '.join(item.get('colors', []))}"
            for item in wardrobe["items"]
        )

        prompt = f"""A user is considering buying this secondhand item:
{item_description}

Their current wardrobe includes:
{wardrobe_lines}

Suggest 1-2 complete outfit combinations using the new item and specific pieces 
from their wardrobe. Name the exact pieces, explain why they work together, and 
note if anything is missing to complete the look."""

    # Step 4 — call LLM and return response
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


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
    """
    # Step 1 — guard against empty outfit
    if not outfit or not outfit.strip():
        return "Couldn't generate a caption — no outfit suggestion was provided."

    # Step 2 — build prompt
    prompt = f"""You are writing an Instagram caption for a thrift outfit post.

The thrifted item is:
- Name: {new_item['title']}
- Price: ${new_item['price']}
- Platform: {new_item['platform']}
- Style: {', '.join(new_item['style_tags'])}
- Colors: {', '.join(new_item['colors'])}

The outfit suggestion is:
{outfit}

Write a 2-4 sentence caption that:
- Sounds casual and authentic, like a real person posting an OOTD
- Mentions the item name, price, and platform naturally once each
- Captures the specific vibe of this outfit
- Does NOT sound like a product description or an ad

Only return the caption text, nothing else."""

    # Step 3 — call LLM with higher temperature for variety
    client = Groq()
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.2
    )

    return response.choices[0].message.content

def score_listing(item: dict, wardrobe: dict, style_profile: dict | None = None) -> dict:
    """
    Score a listing 0-10 based on how much value it adds to the wardrobe.

    Args:
        item:          A listing dict from search_listings.
        wardrobe:      The user's current wardrobe with an 'items' key.
        style_profile: Optional dict of user preferences (colors, styles, categories).

    Returns:
        A dict with:
        - score (float): 0-10 buy confidence
        - reasons (list of str): what raised or lowered the score
        - verdict (str): "strong buy", "maybe", or "pass"
        - low_confidence (bool): True if wardrobe was empty
    """
    reasons = []
    score = 5.0  # start neutral
    low_confidence = False

    # ── Wardrobe checks ───────────────────────────────────────────────────────
    if not wardrobe["items"]:
        low_confidence = True
        reasons.append("Wardrobe is empty — score is based on item and style profile only")
    else:
        # Check how many wardrobe items share style_tags with this item
        item_tags = set(item.get("style_tags", []))
        item_colors = set(item.get("colors", []))
        matches = 0

        for w in wardrobe["items"]:
            wardrobe_tags = set(w.get("style_tags", []))
            wardrobe_colors = set(w.get("colors", []))
            if item_tags & wardrobe_tags or item_colors & wardrobe_colors:
                matches += 1

        if matches >= 3:
            score += 2.0
            reasons.append(f"Pairs with {matches} items already in your wardrobe")
        elif matches >= 1:
            score += 1.0
            reasons.append(f"Pairs with {matches} item(s) in your wardrobe")
        else:
            score -= 1.0
            reasons.append("Doesn't overlap with much in your current wardrobe")

        # Check for category redundancy
        category_count = sum(
            1 for w in wardrobe["items"] if w.get("category") == item.get("category")
        )
        if category_count >= 3:
            score -= 1.5
            reasons.append(f"You already have {category_count} {item['category']} — possible redundancy")
        else:
            score += 0.5
            reasons.append(f"Fills a gap — you only have {category_count} {item['category']}")

    # ── Condition check ───────────────────────────────────────────────────────
    if item.get("condition") == "excellent":
        score += 1.0
        reasons.append("Item is in excellent condition")
    elif item.get("condition") == "fair":
        score -= 1.0
        reasons.append("Item is only in fair condition — inspect carefully")

    # ── Style profile checks (optional) ──────────────────────────────────────
    if style_profile:
        preferred_colors = set(style_profile.get("preferred_colors", []))
        preferred_styles = set(style_profile.get("style_tags", []))

        if preferred_colors & set(item.get("colors", [])):
            score += 1.0
            reasons.append("Matches your preferred colors")

        if preferred_styles & set(item.get("style_tags", [])):
            score += 1.0
            reasons.append("Matches your style preferences")

        avoided = style_profile.get("avoided_categories", [])
        if item.get("category") in avoided:
            score -= 2.0
            reasons.append(f"You've said you don't shop for {item['category']}")
    else:
        reasons.append("No style profile provided — preference scoring skipped")

    # ── Clamp score and assign verdict ────────────────────────────────────────
    score = round(max(0.0, min(10.0, score)), 1)

    if score >= 7.0:
        verdict = "strong buy"
    elif score >= 4.5:
        verdict = "maybe"
    else:
        verdict = "pass"

    return {
        "score": score,
        "reasons": reasons,
        "verdict": verdict,
        "low_confidence": low_confidence
    }

def estimate_price_fairness(item: dict, condition_weight: float = 0.5) -> dict:
    """
    Estimate whether a listing's price is fair based on comparable items.

    Args:
        item:             A listing dict from search_listings.
        condition_weight: 0-1 float controlling how much condition affects
                         the estimate. Defaults to 0.5.

    Returns:
        A dict with:
        - verdict (str): "great deal", "fair price", "overpriced", or "not enough data"
        - average_comparable_price (float): mean price of comparable items
        - comparables_found (int): number of items used in the estimate
        - reasoning (str): plain-English explanation of the verdict
    """
    all_listings = load_listings()
    item_tags = set(item.get("style_tags", []))
    condition_rank = {"excellent": 3, "good": 2, "fair": 1}

    # ── Find comparables ──────────────────────────────────────────────────────
    comparables = []
    for listing in all_listings:
        # skip the item itself
        if listing["id"] == item["id"]:
            continue

        # must be same category
        if listing["category"] != item["category"]:
            continue

        # must share at least 1 style tag
        listing_tags = set(listing.get("style_tags", []))
        if not (item_tags & listing_tags):
            continue

        comparables.append(listing)

    # ── Not enough data ───────────────────────────────────────────────────────
    if len(comparables) < 2:
        reason_parts = []
        if not comparables:
            reason_parts.append(f"no other {item['category']} items share its style tags")
        else:
            reason_parts.append("only 1 comparable item found — not enough for a reliable estimate")

        return {
            "verdict": "not enough data",
            "average_comparable_price": 0.0,
            "comparables_found": len(comparables),
            "reasoning": f"Can't estimate price fairness — {reason_parts[0]}."
        }

    # ── Calculate average price with optional condition weighting ─────────────
    item_condition_rank = condition_rank.get(item.get("condition", "good"), 2)

    weighted_prices = []
    for c in comparables:
        comp_condition_rank = condition_rank.get(c.get("condition", "good"), 2)
        # adjust comparable price based on condition difference
        condition_diff = item_condition_rank - comp_condition_rank
        adjusted_price = c["price"] * (1 + condition_diff * condition_weight * 0.1)
        weighted_prices.append(adjusted_price)

    avg_price = round(sum(weighted_prices) / len(weighted_prices), 2)
    item_price = item["price"]

    # ── Assign verdict ────────────────────────────────────────────────────────
    if item_price <= avg_price * 0.8:
        verdict = "great deal"
    elif item_price <= avg_price * 1.1:
        verdict = "fair price"
    else:
        verdict = "overpriced"

    reasoning = (
        f"{len(comparables)} similar {item['category']} items average ${avg_price} — "
        f"this is priced at ${item_price}. "
        f"Verdict: {verdict}."
    )

    return {
        "verdict": verdict,
        "average_comparable_price": avg_price,
        "comparables_found": len(comparables),
        "reasoning": reasoning
    }

def explain_style_gap(wardrobe: dict) -> dict:
    """
    Analyze the user's wardrobe and identify what's missing.

    Args:
        wardrobe: The user's current wardrobe with an 'items' key.

    Returns:
        A dict with:
        - gaps (list of str): plain-English descriptions of what's missing
        - category_counts (dict): maps each category to how many items the user owns
        - suggested_search (str): a ready-made description to pass into search_listings
    """
    EXPECTED_MINIMUMS = {
        "tops": 2,
        "bottoms": 2,
        "outerwear": 1,
        "shoes": 1,
        "accessories": 1
    }

    # ── Empty wardrobe default ────────────────────────────────────────────────
    if not wardrobe["items"]:
        return {
            "gaps": [
                "No items yet — your wardrobe is empty",
                "Consider starting with a versatile neutral top",
                "A pair of straight-leg jeans works with almost everything",
                "A simple pair of white sneakers ties most outfits together"
            ],
            "category_counts": {cat: 0 for cat in EXPECTED_MINIMUMS},
            "suggested_search": "versatile neutral top"
        }

    # ── Count items per category ──────────────────────────────────────────────
    category_counts = {cat: 0 for cat in EXPECTED_MINIMUMS}
    all_tags = []
    all_colors = []

    for item in wardrobe["items"]:
        cat = item.get("category")
        if cat in category_counts:
            category_counts[cat] += 1
        all_tags.extend(item.get("style_tags", []))
        all_colors.extend(item.get("colors", []))

    # ── Find gaps ─────────────────────────────────────────────────────────────
    gaps = []

    # category gaps
    for cat, minimum in EXPECTED_MINIMUMS.items():
        count = category_counts[cat]
        if count == 0:
            gaps.append(f"No {cat} listed — this is a key missing category")
        elif count < minimum:
            gaps.append(f"Only {count} {cat} — consider adding more variety")

    # versatility gaps
    versatile_tags = ["casual", "layering", "everyday", "versatile"]
    missing_versatile = [t for t in versatile_tags if t not in all_tags]
    if missing_versatile:
        gaps.append(f"Nothing tagged for {', '.join(missing_versatile)} — wardrobe may lack everyday options")

    # color variety gap
    unique_colors = set(all_colors)
    if len(unique_colors) <= 2:
        gaps.append(f"Limited color variety — most items are {', '.join(unique_colors)}")

    # ── Build suggested search from biggest gap ───────────────────────────────
    for cat, minimum in EXPECTED_MINIMUMS.items():
        if category_counts[cat] == 0:
            suggested_search = f"versatile {cat}"
            break
    else:
        suggested_search = "versatile " + max(
            EXPECTED_MINIMUMS,
            key=lambda cat: EXPECTED_MINIMUMS[cat] - category_counts[cat]
        )

    return {
        "gaps": gaps if gaps else ["Wardrobe looks well-rounded — no major gaps found"],
        "category_counts": category_counts,
        "suggested_search": suggested_search
    }