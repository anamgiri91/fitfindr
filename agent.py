"""
agent.py

The FitFindr planning loop. Orchestrates all tools in response to a
natural language user query, passing state between them via a session dict.

Flow (matches architecture diagram):
    User input
      → [optional] explain_style_gap   (if user is unsure what they want)
      → search_listings                 (retries on no results / pass verdict)
      → estimate_price_fairness  ─┐
      → score_listing            ◄┘  (pass → new search; strong buy/maybe → continue)
      → suggest_outfit               (flags partial outfits)
      → create_fit_card              (templated fallback if LLM fails)
      → save session to profile.json (if user does not refine/search again)

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import re
from pathlib import Path

from tools import (
    create_fit_card,
    estimate_price_fairness,
    explain_style_gap,
    score_listing,
    search_listings,
    suggest_outfit,
)


# ── constants ──────────────────────────────────────────────────────────────────

PROFILE_PATH = Path("profile.json")

# Maximum search retries before giving up, to prevent infinite loops.
MAX_SEARCH_RETRIES = 3


# ── session state ──────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict, style_profile: dict | None = None) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    Fields mirror the Session State node in the architecture diagram plus
    the extra bookkeeping needed to drive the loop (query, parsed, error, flags).
    """
    return {
        # ── inputs ─────────────────────────────────────────────────────────────
        "query": query,
        "parsed": {},                  # extracted description / size / max_price

        # ── session state (diagram node) ───────────────────────────────────────
        "wardrobe": wardrobe,
        "style_profile": style_profile or {},
        "search_results": [],
        "selected_item": None,
        "price_verdict": None,         # from estimate_price_fairness
        "score_result": None,          # from score_listing  {"verdict": ..., "reasons": [...]}
        "outfits": [],                 # from suggest_outfit
        "fit_card": None,              # from create_fit_card

        # ── loop bookkeeping ───────────────────────────────────────────────────
        "outfit_complete": None,       # True = complete, False = partial
        "fit_card_fallback": False,    # True when templated fallback was used
        "error": None,                 # set only on unrecoverable failure
        "search_retries": 0,           # guard against infinite search loops
    }


# ── query parsing ──────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(
    r"(?:under|below|max(?:imum)?|less\s+than|<)\s*\$?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SIZE_RE = re.compile(
    # "size M" / "size XL" — explicit prefix, always unambiguous.
    # Bare size token — must be fully isolated from letters and digits on both
    # sides, so "50s", "1990s", and partial words like "trousers" don't match.
    r"(?:size\s+)(XXS|XS|XL|XXL|2XL|3XL|[SML])\b"
    r"|(?<![a-zA-Z0-9])(XXS|XS|XL|XXL|2XL|3XL|[SML])(?![a-zA-Z0-9])",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a", "an", "the", "for", "me", "i", "im", "i'm", "looking",
    "need", "want", "find", "get", "some", "something", "any",
}


def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex. Fast, deterministic, and testable without an LLM call.

    Returns:
        {"description": str, "size": str | None, "max_price": float | None}
    """
    price_match = _PRICE_RE.search(query)
    max_price = float(price_match.group(1)) if price_match else None

    size_match = _SIZE_RE.search(query)
    if size_match:
        # Group 1 = "size XYZ" branch; group 2 = bare isolated size branch.
        size = (size_match.group(1) or size_match.group(2)).upper()
    else:
        size = None

    working = query
    if price_match:
        working = working[:price_match.start()] + " " + working[price_match.end():]
    if size_match:
        working = working[:size_match.start()] + " " + working[size_match.end():]

    tokens = re.findall(r"[a-zA-Z']+", working)
    desc_tokens = [t for t in tokens if t.lower() not in _STOP_WORDS]
    description = " ".join(desc_tokens).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── helpers ────────────────────────────────────────────────────────────────────

def _no_results_message(parsed: dict) -> str:
    """Build a specific, actionable no-results message from parsed params."""
    parts = [f'No listings found for "{parsed["description"]}"']
    if parsed["size"]:
        parts.append(f"in size {parsed['size']}")
    if parsed["max_price"] is not None:
        parts.append(f"under ${parsed['max_price']:.0f}")
    parts.append("— try broadening your size, price, or keywords.")
    return " ".join(parts)


def _save_session(session: dict) -> None:
    """
    Persist the completed session to profile.json.

    Only serialisable fields are written; wardrobe and style_profile are
    omitted because they are loaded from their own files at startup.
    """
    record = {
        "query":             session["query"],
        "parsed":            session["parsed"],
        "selected_item":     session["selected_item"],
        "price_verdict":     session["price_verdict"],
        "score_result":      session["score_result"],
        "outfits":           session["outfits"],
        "outfit_complete":   session["outfit_complete"],
        "fit_card":          session["fit_card"],
        "fit_card_fallback": session["fit_card_fallback"],
    }

    existing: list = []
    if PROFILE_PATH.exists():
        try:
            existing = json.loads(PROFILE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.append(record)
    PROFILE_PATH.write_text(json.dumps(existing, indent=2))


# ── planning loop ──────────────────────────────────────────────────────────────

def run_agent(
    query: str,
    wardrobe: dict,
    style_profile: dict | None = None,
    knows_what_they_want: bool = True,
    save_session: bool = True,
) -> dict:
    """
    Main agent entry point. Runs the full FitFindr planning loop and returns
    the completed session dict.

    Args:
        query:               Natural language user request.
        wardrobe:            User's wardrobe dict.
        style_profile:       Optional persisted style profile dict.
        knows_what_they_want: Pass False to route through explain_style_gap
                             first (the "No" branch in the flowchart).
        save_session:        Write the completed session to profile.json when
                             the loop completes successfully.

    Returns:
        Session dict. Always check session["error"] first — if set, the loop
        ended early and output fields will be None.

    Planning loop (mirrors architecture flowchart):

        [Optional] explain_style_gap  → overwrites parsed description
        ↓
        search_listings               ← retries here on no-results OR pass verdict
        ↓
        estimate_price_fairness  ─┐
        score_listing            ◄┘
          verdict == "pass"       → surface reasons, retry search (≤ MAX_SEARCH_RETRIES)
          verdict == "strong buy"
                 or "maybe"       → continue
        ↓
        suggest_outfit             → flag partial outfits, continue anyway
        ↓
        create_fit_card            → templated fallback on LLM failure
        ↓
        [optional] save session to profile.json
    """
    # ── initialize ─────────────────────────────────────────────────────────────
    session = _new_session(query, wardrobe, style_profile)

    # ── parse query ────────────────────────────────────────────────────────────
    session["parsed"] = _parse_query(query)

    # ── [optional] explain_style_gap ───────────────────────────────────────────
    # "Does the user know what they want?" — No branch in the flowchart.
    # explain_style_gap reads the wardrobe and returns a suggested search string
    # that populates the search query before we call search_listings.
    if not knows_what_they_want:
        gap_result = explain_style_gap(wardrobe=session["wardrobe"])
        # explain_style_gap returns a dict; pull the ready-made search string.
        suggested_search = (gap_result or {}).get("suggested_search", "")
        if suggested_search:
            # Merge: keep any size/price the user did specify; replace description
            # with the gap-derived suggestion.
            session["parsed"]["description"] = suggested_search

    # ── search → price → score loop ────────────────────────────────────────────
    # Retries when:
    #   a) search_listings returns no results, or
    #   b) score_listing returns a "pass" verdict.
    # MAX_SEARCH_RETRIES prevents infinite looping.

    while session["search_retries"] < MAX_SEARCH_RETRIES:
        session["search_retries"] += 1

        # ── search_listings ───────────────────────────────────────────────────
        results = search_listings(
            description=session["parsed"]["description"],
            size=session["parsed"]["size"],
            max_price=session["parsed"]["max_price"],
        )
        session["search_results"] = results

        if not results:
            # Surface a helpful message and return early.
            # In an interactive session the agent would prompt the user to adjust
            # their query and loop; in batch/API mode we terminate here.
            session["error"] = _no_results_message(session["parsed"])
            return session

        # ── select top result ─────────────────────────────────────────────────
        session["selected_item"] = results[0]

        # ── estimate_price_fairness ───────────────────────────────────────────
        # Its verdict feeds into score_listing indirectly: we store the full
        # result in session["price_verdict"] for the fit card / session record,
        # but score_listing in tools.py does not accept it as a parameter.
        price_result = estimate_price_fairness(item=session["selected_item"])
        session["price_verdict"] = price_result

        # ── score_listing ─────────────────────────────────────────────────────
        score_result = score_listing(
            item=session["selected_item"],
            wardrobe=session["wardrobe"],
            style_profile=session["style_profile"],
        )
        session["score_result"] = score_result

        verdict = (score_result or {}).get("verdict", "maybe")

        if verdict == "pass":
            reasons = (score_result or {}).get("reasons", [])
            reason_text = "; ".join(reasons) if reasons else "no specific reason given"

            if session["search_retries"] >= MAX_SEARCH_RETRIES:
                # Exhausted retries — surface the pass reason and stop.
                session["error"] = (
                    f'Top result scored "pass" ({reason_text}). '
                    "No more search retries available — try a different query."
                )
                return session

            # "pass" → loop back to search_listings (diagram node J → E).
            # Surface the reason to the caller via a print; in an interactive
            # session this would be shown to the user before the retry.
            print(
                f"[FitFindr] Item scored 'pass' ({reason_text}). "
                f"Retrying search (attempt {session['search_retries']} of {MAX_SEARCH_RETRIES})…"
            )
            # Clear stale item/score state before the next iteration.
            session["selected_item"] = None
            session["price_verdict"] = None
            session["score_result"] = None
            continue  # retry search

        # verdict is "strong buy" or "maybe" — exit the search/score loop
        break

    else:
        # while condition exhausted without a break (should not normally occur
        # because the "pass" branch returns early once retries are exhausted,
        # but kept as a safety net).
        session["error"] = "Exceeded maximum search retries without finding a suitable item."
        return session

    # ── suggest_outfit ─────────────────────────────────────────────────────────
    outfits = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )
    # suggest_outfit returns a plain string, not a list — store directly.
    outfit_string = outfits if isinstance(outfits, str) else ""
    session["outfits"] = [outfit_string] if outfit_string else []

    # suggest_outfit returns a single string. "Complete" means non-empty;
    # there is no structured missing_categories field to inspect.
    session["outfit_complete"] = bool(session["outfits"] and session["outfits"][0])

    # ── create_fit_card ────────────────────────────────────────────────────────
    outfit_str = session["outfits"][0] if session["outfits"] else ""

    try:
        fit_card = create_fit_card(
            outfit=outfit_str,
            new_item=session["selected_item"],
        )
        if not fit_card:
            raise ValueError("create_fit_card returned an empty result")
        session["fit_card"] = fit_card

    except Exception:
        # Templated fallback — diagram node N.
        item = session["selected_item"]
        title = item.get("title", "this item") if isinstance(item, dict) else "this item"
        price = item.get("price", "?")  if isinstance(item, dict) else "?"
        session["fit_card"] = (
            f"✨ Fit Check: {title} · ${price}\n"
            f"Styled with pieces from your wardrobe.\n"
            f"#ThriftFind #OOTD #FitFindr"
        )
        session["fit_card_fallback"] = True
        print("[FitFindr] Warning: fit card generated from template (LLM call failed).")
    # ── save session ───────────────────────────────────────────────────────────
    # In a fully interactive loop, the agent would ask "search again or refine?"
    # (diagram node P) before saving. In batch/API mode we save unconditionally
    # unless the caller opts out.
    if save_session:
        try:
            _save_session(session)
        except OSError as exc:
            print(f"[FitFindr] Warning: could not save session to profile.json — {exc}")

    return session


# ── CLI test ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
        save_session=False,
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        verdict = (session["score_result"] or {}).get("verdict", "—")
        price_v = (session["price_verdict"] or {}).get("verdict", "—")
        print(f"Found:   {session['selected_item']['title']}")
        print(f"Verdict: {verdict}  |  Price fairness: {price_v}")
        print(f"Outfits: {'complete' if session['outfit_complete'] else 'partial'}")
        if session["fit_card_fallback"]:
            print("(fit card used templated fallback)")
        print(f"\nFit card:\n{session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
        save_session=False,
    )
    print(f"Error: {session2['error']}")

    print("\n\n=== Style gap path (user unsure) ===\n")
    session3 = run_agent(
        query="not sure, help me find something",
        wardrobe=get_example_wardrobe(),
        knows_what_they_want=False,
        save_session=False,
    )
    if session3["error"]:
        print(f"Error: {session3['error']}")
    else:
        print(f"Suggested search used: {session3['parsed']['description']}")
        print(f"Found: {session3['selected_item']['title']}")