"""
Narrative Agent
===============
Writes the plain-English summary that sits at the top of a report.

Everything else in this pipeline is deterministic: the same inputs produce the
same numbers and the same templated prose. This agent is the one place a model
writes, and it is strictly downstream — it reads the structured output the
other agents produced and explains it. It never computes, never fetches, and
never decides the recommendation.

Optional by construction. With no ANTHROPIC_API_KEY configured the agent
reports itself unavailable and the report is generated exactly as before, so
the deterministic pipeline is never blocked on a third-party API.
"""

import json
import logging
from typing import Any, Optional

from ..core.config import settings

logger = logging.getLogger("stock_analyzer.agents.narrative")

# The model is asked to explain figures, never to produce them. Anything it
# cannot support from the payload it is told to omit rather than infer.
SYSTEM_PROMPT = """\
You are an equity analyst writing the opening summary of an automated research \
report. A quantitative pipeline has already done the analysis; your job is to \
explain its conclusions to an investor in plain English.

Ground rules, in order of importance:

1. Use only the figures in the JSON you are given. Never state a number, date, \
ratio or fact that is not present in it. If something you would normally \
mention is missing, leave it out rather than estimating it.
2. Do not change or second-guess the recommendation. Explain why the model \
reached it, including the factors that argued against it.
3. Say what is uncertain. If confidence is low, factor coverage is partial, the \
DCF is unavailable, or the valuation rests mostly on terminal value, that \
belongs in the summary.
4. No hype, no hedging filler, no investment advice framing ("you should buy"). \
Describe what the analysis found.

Write 150-250 words as two or three short paragraphs of flowing prose. No \
headings, no bullet points, no markdown emphasis, no preamble — begin with the \
company and the call.\
"""


class NarrativeUnavailable(Exception):
    """Raised when a narrative cannot be produced. Never fatal to a report."""


class NarrativeAgent:
    """Turns the pipeline's structured output into a written summary."""

    MODEL = "claude-opus-5"
    # Caps thinking plus response text together. A few hundred words of prose at
    # low effort needs far less than this; the headroom keeps a longer-than-usual
    # deliberation from truncating the summary mid-sentence.
    MAX_TOKENS = 4000
    # This is a scoped writing task over data that is already analysed — the
    # reasoning has happened upstream.
    EFFORT = "low"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self._client: Any = None

    @property
    def available(self) -> bool:
        """Whether a narrative can be attempted at all."""
        return bool(self.api_key)

    def _get_client(self) -> Any:
        """
        Build the client lazily.

        Importing at module scope would make anthropic a hard dependency of the
        whole pipeline, which it is not — the feature is off by default.
        """
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover - dependency is installed
                raise NarrativeUnavailable(
                    "The anthropic package is not installed."
                ) from e
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    # ── payload ───────────────────────────────────────────────

    @staticmethod
    def _round(value: Any, places: int = 4) -> Any:
        try:
            return round(float(value), places)
        except (TypeError, ValueError):
            return None

    def build_payload(
        self,
        *,
        ticker: str,
        profile: dict,
        assessment: dict,
        valuation: dict,
        metrics: dict,
        risk: dict,
        peers: dict,
        earnings: dict,
        sentiment: dict,
        current_price: Optional[float],
    ) -> dict[str, Any]:
        """
        Assemble what the model is allowed to talk about.

        Deliberately narrow: the conclusions and the handful of figures behind
        them, not the raw agent dumps. A smaller payload is cheaper, and it
        bounds what the model can misread.
        """
        groups = metrics.get("groups", {})
        sensitivity = valuation.get("sensitivity") or {}

        return {
            "ticker": ticker,
            "company_name": (profile or {}).get("companyName"),
            "sector": (profile or {}).get("sector"),
            "industry": (profile or {}).get("industry"),
            "current_price": self._round(current_price, 2),
            "recommendation": {
                "call": assessment.get("recommendation"),
                "composite_score": assessment.get("composite_score"),
                "confidence_pct": assessment.get("confidence"),
                "factor_coverage": assessment.get("coverage"),
                "rationale": assessment.get("rationale"),
                "factors": [
                    {
                        "name": factor.get("label"),
                        "score": factor.get("score"),
                        "weight": factor.get("weight"),
                        "drivers": factor.get("drivers"),
                    }
                    for factor in assessment.get("factors", [])
                ],
            },
            "valuation": {
                "status": valuation.get("status"),
                "unavailable_reason": valuation.get("error"),
                "dcf_value_per_share": valuation.get("dcf_intrinsic_value_per_share"),
                "range_low": sensitivity.get("low"),
                "range_high": sensitivity.get("high"),
                "wacc": valuation.get("wacc"),
                "assumed_fcf_growth": valuation.get("fcf_growth_rate"),
                "terminal_value_share": valuation.get("terminal_value_share"),
                "caveats": valuation.get("warnings"),
            },
            "multiples": groups.get("valuation", {}),
            "profitability": groups.get("profitability", {}),
            "growth": groups.get("growth", {}),
            "financial_health": {
                **groups.get("liquidity", {}),
                **groups.get("leverage", {}),
            },
            "risk": {
                "rating": risk.get("risk_rating"),
                "annual_volatility": risk.get("annual_volatility"),
                "beta": risk.get("beta"),
                "max_drawdown_pct": risk.get("max_drawdown_pct"),
                "sharpe_ratio": risk.get("sharpe_ratio"),
                "measured_over": risk.get("observations"),
            },
            "peers": {
                "peer_count": peers.get("peer_count"),
                "symbols": [p.get("symbol") for p in peers.get("peers", [])],
                "relative_valuation_score": peers.get("relative_valuation_score"),
                "summary": peers.get("summary"),
                "sector_pe": (peers.get("sector") or {}).get("sector_pe"),
                "vs_sector_pe": (peers.get("sector") or {}).get("vs_sector_pe"),
            },
            "earnings": {
                "next_report_date": earnings.get("next_date"),
                "days_until": earnings.get("days_until"),
                "imminent": earnings.get("is_imminent"),
                "beat_rate": earnings.get("beat_rate"),
            },
            "sentiment": {
                "score": sentiment.get("average_sentiment_compound"),
                "articles": sentiment.get("analyzed_articles_count"),
            },
        }

    # ── generation ────────────────────────────────────────────

    def run(self, payload: dict[str, Any]) -> Optional[str]:
        """
        Write the narrative, or return None if one cannot be produced.

        Returning None rather than raising is deliberate: a report without a
        narrative is a complete report.
        """
        if not self.available:
            logger.info("Narrative skipped: no ANTHROPIC_API_KEY configured.")
            return None

        try:
            return self._generate(payload)
        except NarrativeUnavailable as e:
            logger.warning("Narrative unavailable: %s", e)
        except Exception as e:  # noqa: BLE001 - never fail a report over prose
            logger.error("Narrative generation failed: %s", e, exc_info=True)
        return None

    def _generate(self, payload: dict[str, Any]) -> Optional[str]:
        import anthropic

        client = self._get_client()
        prompt = (
            "Here is the completed analysis as JSON. Write the summary.\n\n"
            f"```json\n{json.dumps(payload, indent=2, default=str)}\n```"
        )

        try:
            response = client.beta.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=SYSTEM_PROMPT,
                output_config={"effort": self.EFFORT},
                # Route a declined request to a fallback model server-side
                # rather than returning nothing; financial and security-adjacent
                # wording occasionally trips a classifier.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.RateLimitError as e:
            raise NarrativeUnavailable(f"Rate limited: {e}") from e
        except anthropic.APIStatusError as e:
            raise NarrativeUnavailable(f"API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise NarrativeUnavailable(f"Could not reach the API: {e}") from e

        # A refusal returns HTTP 200 with empty or partial content, so the
        # stop reason has to be checked before reading any blocks.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise NarrativeUnavailable(f"Model declined the request ({category}).")

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()

        if not text:
            raise NarrativeUnavailable("Model returned no text.")

        if response.stop_reason == "max_tokens":
            # Prose cut mid-sentence reads worse than no prose at all.
            logger.warning("Narrative hit the token cap; discarding the partial summary.")
            raise NarrativeUnavailable("Response exceeded the token limit.")

        logger.info(
            "Narrative generated (%d chars, %d output tokens, model %s)",
            len(text), response.usage.output_tokens, response.model,
        )
        return text
