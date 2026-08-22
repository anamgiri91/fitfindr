"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import os

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.
 
    Args:
        user_query:      The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".
 
    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.
    """
    # 1. Guard against an empty query.
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", ""
 
    # 2. Select wardrobe based on the dropdown choice.
    if wardrobe_choice == "Example wardrobe":
        wardrobe = get_example_wardrobe()
    else:
        wardrobe = get_empty_wardrobe()
 
    # 3. Run the agent.
    session = run_agent(query=user_query, wardrobe=wardrobe, save_session=False)
 
    # 4. Surface any error in the first panel; leave the other two blank.
    if session["error"]:
        return session["error"], "", ""
 
    # 5. Format the selected item into a readable listing_text string.
    item = session["selected_item"]
    score_result = session.get("score_result") or {}
    price_verdict = session.get("price_verdict") or {}
 
    listing_text = (
        f"{item['title']}\n"
        f"{'─' * 40}\n"
        f"Price:     ${item['price']}  ({price_verdict.get('verdict', 'n/a')})\n"
        f"Platform:  {item['platform']}\n"
        f"Condition: {item['condition']}\n"
        f"Size:      {item['size']}\n"
        f"Style:     {', '.join(item.get('style_tags', []))}\n"
        f"Colors:    {', '.join(item.get('colors', []))}\n"
        f"{'─' * 40}\n"
        f"Score: {score_result.get('score', '—')}/10  "
        f"({score_result.get('verdict', '—')})\n"
        + "\n".join("• " + r for r in score_result.get("reasons", []))
    )
 
    outfit_suggestion = session["outfits"][0] if session["outfits"] else ""
 
    return listing_text, outfit_suggestion, session["fit_card"]



# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    # Render (and most PaaS hosts) inject the port to bind to via $PORT and
    # expect the process to listen on 0.0.0.0. Falls back to 7860 for local dev.
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
    )
