from tools import search_listings, score_listing
from tools import suggest_outfit, estimate_price_fairness
from tools import create_fit_card, explain_style_gap
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

def test_search_listings():
    # Test 1 — should return results
    results = search_listings("vintage graphic tee", size="M", max_price=30.0)
    print(f"Test 1 — expected: results, got: {len(results)} items")
    if results:
        print(f"  First result: {results[0]['title']} — ${results[0]['price']}")

    # Test 2 — size filters everything out
    results = search_listings("vintage graphic tee", size="XXXL", max_price=30.0)
    print(f"Test 2 — expected: 0 results, got: {len(results)} items")

    # Test 3 — price filters everything out
    results = search_listings("vintage graphic tee", size="M", max_price=0.01)
    print(f"Test 3 — expected: 0 results, got: {len(results)} items")

    # Test 4 — single word, no filters
    results = search_listings("jacket")
    print(f"Test 4 — expected: results, got: {len(results)} items")

    # Test 5 — gibberish, nothing should match
    results = search_listings("xyzxyzxyz")
    print(f"Test 5 — expected: 0 results, got: {len(results)} items")
    
    '''Output:
    Test 1 — expected: results, got: 2 items
    First result: Y2K Baby Tee — Butterfly Print — $18.0
    Test 2 — expected: 0 results, got: 0 items
    Test 3 — expected: 0 results, got: 0 items
    Test 4 — expected: results, got: 2 items
    Test 5 — expected: 0 results, got: 0 items
    Test 1 — with wardrobe: Based on the Y2K Baby Tee, I suggest two complete outfit combinations:

    '''


def test_suggest_outfit():
    # grab a sample item from search_listings to use as new_item
    results = search_listings("vintage tee", size="M", max_price=50.0)
    new_item = results[0] if results else search_listings("jacket")[0]

    # Test 1 — wardrobe with items, should return specific combinations
    wardrobe = get_example_wardrobe()
    result = suggest_outfit(new_item, wardrobe)
    print(f"Test 1 — with wardrobe: {result[:200]}...")

    # Test 2 — empty wardrobe, should return general advice not crash
    empty = get_empty_wardrobe()
    result = suggest_outfit(new_item, empty)
    print(f"Test 2 — empty wardrobe: {result[:200]}...")
    assert len(result) > 0, "should never return empty string"

    '''Output:
    1. **Casual Y2K Look**: Pair the Y2K Baby Tee with the Baggy straight-leg jeans (dark wash) and the Chunky white sneakers. This ...
    Test 2 — empty wardrobe: This Y2K baby tee suits a casual, everyday vibe. To pair well with it, consider adding:

    * High-waisted jeans or a flowy skirt for a cute, laid-back look
    * A pair of distressed denim shorts for a summ...
    '''

def test_create_fit_card():
    # get a real item and outfit to work with
    results = search_listings("vintage tee", size="M", max_price=50.0)
    new_item = results[0] if results else search_listings("jacket")[0]
    wardrobe = get_example_wardrobe()
    outfit = suggest_outfit(new_item, wardrobe)

    # Test 1 — normal input, should return a caption
    result = create_fit_card(outfit, new_item)
    print(f"Test 1 — caption: {result}")

    # Test 2 — run again to confirm output is different each time
    result2 = create_fit_card(outfit, new_item)
    print(f"Test 2 — different caption: {result2}")

    # Test 3 — empty outfit string, should return error message not crash
    result3 = create_fit_card("", new_item)
    print(f"Test 3 — empty outfit: {result3}")
    assert "Couldn't" in result3, "should return error message for empty outfit"
    '''Output:
    Test 1 — caption: Just scored the cutest Y2K Baby Tee — Butterfly Print for $18.0 on depop and I'm obsessed with how it adds a touch of whimsy to my outfits. I've been pairing it with baggy jeans and chunky sneakers for a casual Y2K vibe, but it also looks adorable with khaki trousers and combat boots for a cottagecore-inspired look. The mix of white, pink, and purple hues is giving me all the nostalgic feels.
    Test 2 — different caption: Just thrifted the cutest Y2K Baby Tee — Butterfly Print on Depop for $18.0 and I'm obsessed with how it adds a touch of vintage charm to my outfits. I've been pairing it with everything from baggy jeans and chunky sneakers for a casual Y2K look to wide-leg khaki trousers and combat boots for a cottagecore vibe. The mix of white, pink, and purple hues is giving me all the whimsical feels.
    Test 3 — empty outfit: Couldn't generate a caption — no outfit suggestion was provided.
    '''

def test_score_listing():
    results = search_listings("vintage tee", size="M", max_price=50.0)
    item = results[0] if results else search_listings("jacket")[0]
    wardrobe = get_example_wardrobe()

    style_profile = {
        "preferred_colors": ["black", "white"],
        "style_tags": ["vintage", "streetwear"],
        "avoided_categories": ["accessories"]
    }

    # Test 1 — full inputs, should return a scored result
    result = score_listing(item, wardrobe, style_profile)
    print(f"Test 1 — score: {result['score']}, verdict: {result['verdict']}")
    print(f"  Reasons: {result['reasons']}")

    # Test 2 — empty wardrobe, should flag low confidence
    from utils.data_loader import get_empty_wardrobe
    result = score_listing(item, get_empty_wardrobe(), style_profile)
    print(f"Test 2 — low confidence: {result['low_confidence']}, score: {result['score']}")

    # Test 3 — no style profile, should skip preference scoring without crashing
    result = score_listing(item, wardrobe, None)
    print(f"Test 3 — no profile: {result['score']}, verdict: {result['verdict']}")

    '''Output:
    Test 1 — score: 8.5, verdict: strong buy
    Reasons: ['Pairs with 3 items already in your wardrobe', 'You already have 3 tops — possible redundancy', 'Item is in excellent condition', 'Matches your preferred colors', 'Matches your style preferences']
    Test 2 — low confidence: True, score: 8.0
    Test 3 — no profile: 6.5, verdict: maybe
    '''

def test_estimate_price_fairness():
    # Test 1 — common item, should find comparables
    results = search_listings("vintage tee", size="M", max_price=50.0)
    item = results[0] if results else search_listings("jacket")[0]
    result = estimate_price_fairness(item)
    print(f"Test 1 — verdict: {result['verdict']}")
    print(f"  {result['reasoning']}")
    print(f"  Comparables found: {result['comparables_found']}")

    # Test 2 — condition weight at 0, should ignore condition entirely
    result = estimate_price_fairness(item, condition_weight=0.0)
    print(f"Test 2 — no condition weight: {result['verdict']}, avg: ${result['average_comparable_price']}")

    # Test 3 — niche item that may not have enough comparables
    niche_results = search_listings("sequin blazer")
    if niche_results:
        result = estimate_price_fairness(niche_results[0])
        print(f"Test 3 — niche item: {result['verdict']}, comparables: {result['comparables_found']}")
    else:
        print("Test 3 — no niche item found to test with")
        '''
        Output: Test 1 — verdict: great deal
        14 similar tops items average $22.79 — this is priced at $18.0. Verdict: great deal.
        Comparables found: 14
        Test 2 — no condition weight: fair price, avg: $22.0
        Test 3 — no niche item found to test with
        '''

def test_explain_style_gap():
    # Test 1 — empty wardrobe, should return default starter list
    from utils.data_loader import get_empty_wardrobe
    result = explain_style_gap(get_empty_wardrobe())
    print(f"Test 1 — empty wardrobe gaps: {result['gaps']}")
    print(f"  Suggested search: {result['suggested_search']}")
    assert len(result['gaps']) > 0, "should always return at least one gap"

    # Test 2 — example wardrobe, should identify real gaps
    from utils.data_loader import get_example_wardrobe
    result = explain_style_gap(get_example_wardrobe())
    print(f"Test 2 — example wardrobe gaps: {result['gaps']}")
    print(f"  Category counts: {result['category_counts']}")
    print(f"  Suggested search: {result['suggested_search']}")

if __name__ == "__main__":
    test_search_listings()
    test_suggest_outfit()
    test_create_fit_card()
    test_score_listing()
    test_estimate_price_fairness()
    test_explain_style_gap()