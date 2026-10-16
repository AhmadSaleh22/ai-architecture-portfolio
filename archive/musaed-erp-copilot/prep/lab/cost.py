"""
Back-of-the-envelope cost model for Musaed. Architects are expected to show this math.

Prices change often: look up the current per-million-token prices of the models you are
comparing and pass them in. Defaults below are PLACEHOLDERS, not real prices.

    python cost.py --price-in 3 --price-out 15
    python cost.py --users 1400 --adoption 0.6 --q-per-user-week 5 --price-in 0.5 --price-out 1.5
"""
import argparse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=1400)
    ap.add_argument("--adoption", type=float, default=0.3, help="share of employees using it weekly")
    ap.add_argument("--q-per-user-week", type=float, default=4)
    ap.add_argument("--in-tok", type=int, default=1800, help="system + context + question + history")
    ap.add_argument("--out-tok", type=int, default=250)
    ap.add_argument("--tool-share", type=float, default=0.35, help="questions answered by tools (cheaper)")
    ap.add_argument("--price-in", type=float, default=1.0, help="USD per 1M input tokens (PLACEHOLDER)")
    ap.add_argument("--price-out", type=float, default=5.0, help="USD per 1M output tokens (PLACEHOLDER)")
    ap.add_argument("--cache-hit", type=float, default=0.0, help="share of input tokens served from prompt cache")
    ap.add_argument("--cache-discount", type=float, default=0.9)
    a = ap.parse_args()

    q_month = a.users * a.adoption * a.q_per_user_week * 4.33
    rag_q = q_month * (1 - a.tool_share)
    tool_q = q_month * a.tool_share
    eff_in = a.in_tok * (1 - a.cache_hit * a.cache_discount)
    per_rag = (eff_in * a.price_in + a.out_tok * a.price_out) / 1e6
    per_tool = (400 * a.price_in + 120 * a.price_out) / 1e6  # small routing/formatting call
    monthly = rag_q * per_rag + tool_q * per_tool
    peak_qpm = q_month / 22 / 8 / 60 * 6  # 22 workdays, 8h, x6 month-end payroll peak

    print(f"Questions / month      : {q_month:,.0f}  (RAG {rag_q:,.0f}, tools {tool_q:,.0f})")
    print(f"Cost / RAG question    : ${per_rag:.5f}")
    print(f"Cost / tool question   : ${per_tool:.5f}")
    print(f"LLM cost / month       : ${monthly:,.2f}")
    print(f"LLM cost / user / month: ${monthly / (a.users * a.adoption):.3f}")
    print(f"Peak load (month-end)  : ~{peak_qpm:.1f} questions/min")
    print("\nWhat to try: double --in-tok (bigger context), add --cache-hit 0.6, raise --adoption to 0.8.")
    print("Then ask: at what volume does self-hosting (fixed GPU cost) beat the API? That's an ADR.")


if __name__ == "__main__":
    main()
