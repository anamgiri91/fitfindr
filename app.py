"""
app.py

Gradio interface for FitFindr — a thrift-fashion AI agent. Renders results
as styled HTML cards instead of plain text boxes, on a warm secondhand /
vintage-market visual theme.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import html
import os

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── verdict → badge color ───────────────────────────────────────────────────

SCORE_BADGE = {
    "strong buy": ("#2F6B3A", "#E7F3E8"),   # deep green / pale green
    "maybe":      ("#9A6B14", "#FBF0DA"),   # amber / pale amber
    "pass":       ("#A13A3A", "#FBEAEA"),   # rust red / pale red
}
PRICE_BADGE = {
    "great deal":     ("#2F6B3A", "#E7F3E8"),
    "fair price":     ("#9A6B14", "#FBF0DA"),
    "overpriced":     ("#A13A3A", "#FBEAEA"),
    "not enough data": ("#6B6459", "#EFEAE1"),
}

PLACEHOLDER_CARD = """
<div class="ff-card ff-placeholder">
  <div class="ff-placeholder-icon">{icon}</div>
  <p>{text}</p>
</div>
"""


def _badge(label: str, mapping: dict) -> str:
    fg, bg = mapping.get(label.lower(), ("#6B6459", "#EFEAE1"))
    return (
        f'<span class="ff-badge" style="color:{fg}; background:{bg};">'
        f"{html.escape(label.title())}</span>"
    )


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _error_card(message: str) -> str:
    return f"""
    <div class="ff-card ff-error">
      <div class="ff-error-icon">⚠️</div>
      <p>{_esc(message)}</p>
    </div>
    """


def _listing_card(item: dict, score_result: dict, price_verdict: dict) -> str:
    style_tags = "".join(
        f'<span class="ff-chip">{_esc(t)}</span>' for t in item.get("style_tags", [])
    )
    colors = ", ".join(item.get("colors", [])) or "—"
    reasons = "".join(f"<li>{_esc(r)}</li>" for r in score_result.get("reasons", []))
    score = score_result.get("score", "—")
    score_verdict = score_result.get("verdict", "n/a")
    price_v = price_verdict.get("verdict", "n/a")

    return f"""
    <div class="ff-card">
      <div class="ff-card-top">
        <h3 class="ff-title">{_esc(item['title'])}</h3>
        <div class="ff-price">${_esc(item['price'])}</div>
      </div>
      <div class="ff-badge-row">
        {_badge(score_verdict, SCORE_BADGE)}
        {_badge(price_v, PRICE_BADGE)}
      </div>
      <div class="ff-meta-grid">
        <div><span class="ff-meta-label">Platform</span>{_esc(item['platform']).title()}</div>
        <div><span class="ff-meta-label">Condition</span>{_esc(item['condition']).title()}</div>
        <div><span class="ff-meta-label">Size</span>{_esc(item['size'])}</div>
        <div><span class="ff-meta-label">Colors</span>{_esc(colors)}</div>
      </div>
      <div class="ff-chip-row">{style_tags}</div>
      <hr class="ff-divider"/>
      <div class="ff-score-row">
        <div class="ff-score-num">{_esc(score)}<span>/10</span></div>
        <ul class="ff-reasons">{reasons}</ul>
      </div>
    </div>
    """


def _outfit_card(outfit_text: str, complete: bool) -> str:
    tag = "" if complete else '<span class="ff-chip ff-chip-warn">partial outfit</span>'
    body = _esc(outfit_text).replace("\n", "<br/>") if outfit_text else "No outfit could be generated."
    return f"""
    <div class="ff-card">
      <div class="ff-card-top">
        <h3 class="ff-title">Outfit idea</h3>
        {tag}
      </div>
      <p class="ff-body">{body}</p>
    </div>
    """


def _fitcard_card(fit_card_text: str, fallback: bool) -> str:
    tag = '<span class="ff-chip ff-chip-warn">template fallback</span>' if fallback else ""
    body = _esc(fit_card_text).replace("\n", "<br/>") if fit_card_text else ""
    return f"""
    <div class="ff-card ff-fitcard">
      <div class="ff-card-top">
        <h3 class="ff-title">Your fit card ✨</h3>
        {tag}
      </div>
      <p class="ff-body ff-caption">{body}</p>
    </div>
    """


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    if not user_query or not user_query.strip():
        msg = _error_card("Please enter a search query.")
        return msg, PLACEHOLDER_CARD.format(icon="👗", text="Waiting on a search…"), \
               PLACEHOLDER_CARD.format(icon="✨", text="Your fit card will appear here.")

    wardrobe = get_example_wardrobe() if wardrobe_choice == "Example wardrobe" else get_empty_wardrobe()

    session = run_agent(query=user_query, wardrobe=wardrobe, save_session=False)

    if session["error"]:
        empty = PLACEHOLDER_CARD.format(icon="—", text="No result for this search.")
        return _error_card(session["error"]), empty, empty

    item = session["selected_item"]
    score_result = session.get("score_result") or {}
    price_verdict = session.get("price_verdict") or {}

    listing_html = _listing_card(item, score_result, price_verdict)

    outfit_text = session["outfits"][0] if session["outfits"] else ""
    outfit_html = _outfit_card(outfit_text, session.get("outfit_complete", False))

    fitcard_html = _fitcard_card(session["fit_card"], session.get("fit_card_fallback", False))

    return listing_html, outfit_html, fitcard_html


# ── theme + styling ─────────────────────────────────────────────────────────

THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.orange,
    secondary_hue=gr.themes.colors.stone,
    neutral_hue=gr.themes.colors.stone,
    font=[gr.themes.GoogleFont("Fraunces"), "ui-serif", "Georgia", "serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
).set(
    body_background_fill="#FAF6F0",
    background_fill_primary="#FFFFFF",
    background_fill_secondary="#F3EDE3",
    border_color_primary="#E4DACB",
    button_primary_background_fill="#C1622D",
    button_primary_background_fill_hover="#A94F21",
    button_primary_text_color="#FFFFFF",
    block_title_text_color="#3D372E",
    block_label_text_color="#7A6F5D",
)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');

.gradio-container {
    font-family: 'Inter', sans-serif !important;
    max-width: 1180px !important;
    margin: 0 auto !important;
}

/* Hero header */
#ff-hero {
    text-align: center;
    padding: 2.2rem 1rem 1.2rem 1rem;
}
#ff-hero h1 {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 2.6rem;
    color: #3D372E;
    margin-bottom: 0.3rem;
    letter-spacing: -0.01em;
}
#ff-hero p {
    color: #7A6F5D;
    font-size: 1.05rem;
    max-width: 560px;
    margin: 0 auto;
}
#ff-hero .ff-tagline-chip {
    display: inline-block;
    margin-top: 0.9rem;
    padding: 0.3rem 0.9rem;
    background: #F3EDE3;
    border: 1px solid #E4DACB;
    border-radius: 999px;
    font-size: 0.8rem;
    color: #A94F21;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    font-weight: 600;
}

/* Search bar area */
#ff-search-row {
    background: #FFFFFF;
    border: 1px solid #E4DACB;
    border-radius: 18px;
    padding: 1.1rem;
    box-shadow: 0 2px 14px rgba(61, 55, 46, 0.05);
}

/* Result cards */
.ff-card {
    background: #FFFFFF;
    border: 1px solid #E4DACB;
    border-radius: 16px;
    padding: 1.3rem 1.4rem;
    min-height: 260px;
    box-shadow: 0 2px 10px rgba(61, 55, 46, 0.04);
}
.ff-card-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
    flex-wrap: wrap;
}
.ff-title {
    font-family: 'Fraunces', serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: #3D372E;
    margin: 0;
    line-height: 1.3;
}
.ff-price {
    font-family: 'Fraunces', serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: #C1622D;
    white-space: nowrap;
}
.ff-badge-row {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.55rem;
    flex-wrap: wrap;
}
.ff-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
}
.ff-meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem 1rem;
    margin-top: 0.9rem;
    font-size: 0.9rem;
    color: #3D372E;
}
.ff-meta-label {
    display: block;
    font-size: 0.7rem;
    color: #9A8F7C;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 0.1rem;
}
.ff-chip-row {
    margin-top: 0.8rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
}
.ff-chip {
    background: #F3EDE3;
    color: #6B6459;
    font-size: 0.75rem;
    padding: 0.22rem 0.6rem;
    border-radius: 999px;
    border: 1px solid #E4DACB;
}
.ff-chip-warn {
    background: #FBF0DA;
    color: #9A6B14;
    border-color: #F0DDB0;
}
.ff-divider {
    border: none;
    border-top: 1px solid #EFE8DB;
    margin: 1rem 0 0.9rem 0;
}
.ff-score-row {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
}
.ff-score-num {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 1.8rem;
    color: #3D372E;
    white-space: nowrap;
}
.ff-score-num span {
    font-size: 1rem;
    font-weight: 400;
    color: #9A8F7C;
}
.ff-reasons {
    margin: 0.15rem 0 0 0;
    padding-left: 1.1rem;
    font-size: 0.87rem;
    color: #57503F;
    line-height: 1.5;
}
.ff-body {
    margin-top: 0.9rem;
    font-size: 0.93rem;
    line-height: 1.6;
    color: #3D372E;
}
.ff-fitcard {
    background: linear-gradient(160deg, #FFF8F0 0%, #FDF1E4 100%);
    border-color: #F0DDB0;
}
.ff-caption {
    font-family: 'Fraunces', serif;
    font-style: italic;
    font-size: 1.02rem;
    color: #5A4A2E;
}
.ff-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #B3A990;
    min-height: 260px;
}
.ff-placeholder-icon {
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
    opacity: 0.6;
}
.ff-error {
    border-color: #F0C9C9;
    background: #FBEAEA;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    min-height: unset;
}
.ff-error-icon {
    font-size: 1.4rem;
}
.ff-error p {
    color: #A13A3A;
    margin: 0;
    font-size: 0.93rem;
}

/* Footer */
#ff-footer {
    text-align: center;
    margin-top: 1.6rem;
    padding: 1.2rem 0 0.6rem 0;
    border-top: 1px solid #E4DACB;
    color: #9A8F7C;
    font-size: 0.85rem;
}
#ff-footer a {
    color: #C1622D;
    text-decoration: none;
    font-weight: 600;
}
#ff-footer a:hover {
    text-decoration: underline;
}
#ff-stack-row {
    display: flex;
    justify-content: center;
    gap: 0.4rem;
    flex-wrap: wrap;
    margin-bottom: 0.7rem;
}
"""

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

STACK_CHIPS = ["Python", "Groq · Llama 3.3 70B", "Gradio", "Agentic tool-calling"]


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.HTML(
            """
            <div id="ff-hero">
              <h1>FitFindr 🛍️</h1>
              <p>A secondhand shopping agent that finds a piece, checks if the price is fair,
                 scores it against your wardrobe, and styles a full outfit around it — automatically.</p>
              <span class="ff-tagline-chip">AI Shopping Agent</span>
            </div>
            """
        )

        with gr.Group(elem_id="ff-search-row"):
            with gr.Row():
                query_input = gr.Textbox(
                    label="What are you looking for?",
                    placeholder="e.g. vintage graphic tee under $30, size M",
                    lines=2,
                    scale=3,
                    container=True,
                )
                wardrobe_choice = gr.Radio(
                    choices=["Example wardrobe", "Empty wardrobe (new user)"],
                    value="Example wardrobe",
                    label="Wardrobe",
                    scale=1,
                )
            submit_btn = gr.Button("Find it →", variant="primary", size="lg")

            gr.Examples(
                examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
                inputs=[query_input, wardrobe_choice],
                label="Try one of these",
            )

        with gr.Row(equal_height=True):
            listing_output = gr.HTML(
                PLACEHOLDER_CARD.format(icon="🛍️", text="Your top listing will show up here.")
            )
            outfit_output = gr.HTML(
                PLACEHOLDER_CARD.format(icon="👗", text="An outfit built around it goes here.")
            )
            fitcard_output = gr.HTML(
                PLACEHOLDER_CARD.format(icon="✨", text="A ready-to-post caption goes here.")
            )

        gr.HTML(
            f"""
            <div id="ff-footer">
              <div id="ff-stack-row">
                {''.join(f'<span class="ff-chip">{c}</span>' for c in STACK_CHIPS)}
              </div>
              Built by <a href="https://github.com/anamgiri91" target="_blank">Anam Giri</a>
              — <a href="https://github.com/anamgiri91/fitfindr" target="_blank">source on GitHub</a>
            </div>
            """
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
        theme=THEME,
        css=CSS,
    )
