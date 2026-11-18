"""
"Negotiate" tab for the Space's web UI: a person plays the agent's side.

OpenEnv's auto-generated Playground shows the `offer` field as one plain text
box, but an offer is a dict with a value for each of the 5 issues. Typing a
number there failed validation ("Input should be a valid dictionary"). This tab
gives one slider per issue and plain-language feedback instead.
"""

from typing import Any, Dict, List, Optional

import gradio as gr

# (name, label, what the 0-1 scale means), matching ISSUES in environment.py.
ISSUES = [
    ("price", "Price", "0 = lowest, 1 = highest"),
    ("quantity", "Quantity", "0.1 = 1 unit, 1.0 = 10 units"),
    ("delivery_days", "Delivery time", "0 = 1 day, 1 = 60 days"),
    ("warranty_months", "Warranty", "0 = none, 1 = 36 months"),
    ("payment_terms", "Payment terms", "0 = upfront, 1 = instalments"),
]
ISSUE_LABELS = {name: label for name, label, _ in ISSUES}

# Which end of each scale the buyer prefers (rewards.py: _party_prefers_low).
BUYER_PREFERS_LOW = {
    "price": True,
    "quantity": False,
    "delivery_days": True,
    "warranty_months": False,
    "payment_terms": False,
}

INTRO = """
### Negotiate a supply deal against a scripted opponent
This is the environment I use to benchmark LLM agents. Here **you** play the agent.

1. Click **Start a new negotiation**. You get a random role (buyer or seller) and private priorities.
2. Each round, set the five terms with the sliders and click **Make offer**, or respond to the
   opponent's last offer with **Accept** or **Walk away**.
3. Your score is mostly how good the final deal is for you, given your priorities, plus a smaller part
   for an efficient deal and sensible concessions. Walking away or running out of rounds scores close to zero.
"""


def _fmt(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _wants(issue: str, role: str) -> str:
    prefers_low = BUYER_PREFERS_LOW[issue]
    if role == "seller":
        prefers_low = not prefers_low
    return "lower" if prefers_low else "higher"


def _offer_table(offer: Dict[str, float]) -> List[str]:
    rows = ["| Term | Value |", "|---|---|"]
    for name, label, _ in ISSUES:
        if name in offer:
            rows.append(f"| {label} | {offer[name]:.2f} |")
    return rows


def render(result: Dict[str, Any]) -> str:
    """Turn a reset/step result into a short Markdown status for a person."""
    obs = result.get("observation", {})
    role = obs.get("agent_role", "?")
    lines = [
        f"**You are the {role}.** Round {obs.get('round_number')} of {obs.get('max_rounds')}"
        f" ({obs.get('rounds_remaining')} left).",
        "",
        "**What matters to you** (your weights, private):",
        "",
        "| Term | Weight | You want it |",
        "|---|---|---|",
    ]
    weights = obs.get("agent_weights") or {}
    for name, label, scale in ISSUES:
        if name in weights:
            lines.append(f"| {label} ({scale}) | {weights[name]:.0%} | {_wants(name, role)} |")

    last_action = obs.get("counterpart_last_action")
    their_offer = obs.get("counterpart_last_offer")
    lines += ["", f"**Opponent's last move:** {last_action or 'none yet'}"]
    if their_offer:
        lines += [""] + _offer_table(their_offer)
        lines += [
            "",
            f"Accepting their offer would be worth **{_fmt(obs.get('agent_utility_if_accept'))}** to you"
            f" (your minimum acceptable is about {_fmt(obs.get('agent_reservation_utility'))}).",
        ]
    if obs.get("agent_utility_of_last_offer") is not None:
        lines.append(f"Your last offer was worth {_fmt(obs.get('agent_utility_of_last_offer'))} to you.")
    if obs.get("message"):
        lines += ["", f"> {obs['message']}"]
    if result.get("done"):
        lines += ["", f"### Negotiation over. Your score: {_fmt(result.get('reward'))}",
                  "Click **Start a new negotiation** to play again."]
    return "\n".join(lines)


def build_negotiate_tab(web_manager, action_fields, metadata, is_chat_env, title, quick_start_md):
    """gradio_builder for openenv's create_app: returns the Negotiate tab."""

    async def start():
        try:
            return render(await web_manager.reset_environment())
        except Exception as e:  # show the problem instead of a stack trace
            return f"Could not start a negotiation: {e}"

    async def act(action: Dict[str, Any]):
        try:
            return render(await web_manager.step_environment(action))
        except Exception as e:
            return (f"That move didn't go through: {e}\n\n"
                    "If no negotiation is running, click **Start a new negotiation** first.")

    async def make_offer(message, *values):
        offer = {name: float(v) for (name, _, _), v in zip(ISSUES, values)}
        action = {"action_type": "offer", "offer": offer}
        if message and message.strip():
            action["message"] = message.strip()[:500]
        return await act(action)

    async def accept():
        return await act({"action_type": "accept"})

    async def walk_away():
        return await act({"action_type": "reject"})

    with gr.Blocks() as blocks:
        gr.Markdown(INTRO)
        with gr.Row():
            with gr.Column(scale=1):
                start_btn = gr.Button("Start a new negotiation", variant="primary")
                sliders = [
                    gr.Slider(minimum=0.1 if name == "quantity" else 0.0, maximum=1.0,
                              value=0.5, step=0.05, label=f"{label} ({scale})")
                    for name, label, scale in ISSUES
                ]
                message = gr.Textbox(label="Message to the opponent (optional)", max_lines=2)
                with gr.Row():
                    offer_btn = gr.Button("Make offer", variant="primary")
                    accept_btn = gr.Button("Accept their offer")
                    reject_btn = gr.Button("Walk away", variant="stop")
            with gr.Column(scale=1):
                status = gr.Markdown("Click **Start a new negotiation** to begin.")

        start_btn.click(start, outputs=status)
        offer_btn.click(make_offer, inputs=[message, *sliders], outputs=status)
        accept_btn.click(accept, outputs=status)
        reject_btn.click(walk_away, outputs=status)
    return blocks
