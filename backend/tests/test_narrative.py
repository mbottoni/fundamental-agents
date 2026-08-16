"""
Tests for the optional narrative summary.

The feature must be invisible when unconfigured and non-fatal when it fails —
a report without a summary is a complete report.
"""

import pytest

from app.agents.narrative_agent import NarrativeAgent, NarrativeUnavailable
from app.agents.synthesis_reporting_agent import SynthesisReportingAgent
from tests.test_recommendation import metrics_payload, sentiment_payload, technical_payload


class FakeBlock:
    def __init__(self, text: str, type: str = "text"):
        self.text = text
        self.type = type


class FakeUsage:
    output_tokens = 210


class FakeResponse:
    def __init__(self, blocks, stop_reason="end_turn", stop_details=None):
        self.content = blocks
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self.usage = FakeUsage()
        self.model = "claude-opus-5"


class FakeMessages:
    """Records the request and replays a canned response."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def stub_client(agent: NarrativeAgent, response=None, error=None) -> FakeMessages:
    messages = FakeMessages(response=response, error=error)
    agent._client = type("C", (), {"beta": type("B", (), {"messages": messages})()})()
    return messages


@pytest.fixture
def payload() -> dict:
    return NarrativeAgent(api_key="test-key").build_payload(
        ticker="AAPL",
        profile={"companyName": "Apple Inc.", "sector": "Technology"},
        assessment={
            "recommendation": "hold",
            "composite_score": 0.18,
            "confidence": 70,
            "coverage": 1.0,
            "rationale": "supported by strong profitability, offset by valuation",
            "factors": [{"label": "Valuation", "score": -0.5, "weight": 0.3, "drivers": ["P/E of 35"]}],
        },
        valuation={
            "status": "ok",
            "dcf_intrinsic_value_per_share": 111.0,
            "sensitivity": {"low": 72.0, "high": 201.0},
            "wacc": 0.08,
            "warnings": [],
        },
        metrics=metrics_payload(),
        risk={"risk_rating": "low", "beta": 0.7},
        peers={"peer_count": 4, "peers": [{"symbol": "MSFT"}], "summary": "trades at a premium"},
        earnings={"next_date": "2026-10-29", "days_until": 74, "is_imminent": False},
        sentiment=sentiment_payload(),
        current_price=305.93,
    )


class TestAvailability:
    def test_disabled_without_an_api_key(self, payload):
        agent = NarrativeAgent(api_key="")
        assert agent.available is False
        assert agent.run(payload) is None

    def test_no_client_is_constructed_when_disabled(self, payload):
        """The feature must not require the SDK to be reachable at all."""
        agent = NarrativeAgent(api_key="")
        agent.run(payload)
        assert agent._client is None

    def test_enabled_with_a_key(self):
        assert NarrativeAgent(api_key="test-key").available is True


class TestPayload:
    def test_conclusions_and_their_drivers_are_included(self, payload):
        assert payload["ticker"] == "AAPL"
        assert payload["recommendation"]["call"] == "hold"
        assert payload["valuation"]["dcf_value_per_share"] == 111.0
        assert payload["peers"]["peer_count"] == 4

    def test_raw_agent_dumps_are_not_included(self, payload):
        """A narrow payload is cheaper and bounds what the model can misread."""
        for key in ("prices", "financials", "news", "benchmark_prices"):
            assert key not in payload

    def test_an_unavailable_dcf_carries_its_reason(self):
        payload = NarrativeAgent(api_key="k").build_payload(
            ticker="X", profile={}, assessment={}, metrics={}, risk={}, peers={},
            earnings={}, sentiment={}, current_price=None,
            valuation={"status": "unavailable", "error": "negative free cash flow"},
        )
        assert payload["valuation"]["unavailable_reason"] == "negative free cash flow"


class TestGeneration:
    def test_text_blocks_are_returned(self, payload):
        agent = NarrativeAgent(api_key="test-key")
        stub_client(agent, FakeResponse([FakeBlock("Apple is fairly valued.")]))
        assert agent.run(payload) == "Apple is fairly valued."

    def test_request_is_grounded_and_scoped(self, payload):
        agent = NarrativeAgent(api_key="test-key")
        messages = stub_client(agent, FakeResponse([FakeBlock("Summary.")]))
        agent.run(payload)

        request = messages.calls[0]
        assert request["model"] == "claude-opus-5"
        assert "only the figures" in request["system"].lower()
        assert request["output_config"]["effort"] == "low"
        # The payload must actually reach the model.
        assert "AAPL" in request["messages"][0]["content"]

    def test_non_text_blocks_are_ignored(self, payload):
        agent = NarrativeAgent(api_key="test-key")
        stub_client(
            agent,
            FakeResponse([FakeBlock("", type="thinking"), FakeBlock("The summary.")]),
        )
        assert agent.run(payload) == "The summary."

    def test_a_refusal_yields_no_narrative(self, payload):
        """A refusal is HTTP 200 with empty content — it must not read as success."""
        agent = NarrativeAgent(api_key="test-key")
        stub_client(agent, FakeResponse([], stop_reason="refusal"))
        assert agent.run(payload) is None

    def test_a_truncated_summary_is_discarded(self, payload):
        """Prose cut mid-sentence reads worse than no prose."""
        agent = NarrativeAgent(api_key="test-key")
        stub_client(agent, FakeResponse([FakeBlock("Apple is fairly val")], stop_reason="max_tokens"))
        assert agent.run(payload) is None

    def test_an_empty_response_yields_no_narrative(self, payload):
        agent = NarrativeAgent(api_key="test-key")
        stub_client(agent, FakeResponse([FakeBlock("   ")]))
        assert agent.run(payload) is None

    def test_provider_errors_are_swallowed(self, payload):
        agent = NarrativeAgent(api_key="test-key")
        stub_client(agent, error=RuntimeError("connection reset"))
        assert agent.run(payload) is None

    def test_a_missing_sdk_is_not_fatal(self, payload, monkeypatch):
        agent = NarrativeAgent(api_key="test-key")

        def no_sdk():
            raise NarrativeUnavailable("The anthropic package is not installed.")

        monkeypatch.setattr(agent, "_get_client", no_sdk)
        assert agent.run(payload) is None


class TestReportRendering:
    @pytest.fixture
    def raw_data(self) -> dict:
        return {
            "ticker": "TEST",
            "profile": {"companyName": "Test Co"},
            "prices": [{"date": "2026-08-14", "close": 100.0}],
        }

    def render(self, raw_data, narrative):
        return SynthesisReportingAgent().run(
            raw_data=raw_data,
            metrics=metrics_payload(),
            sentiment=sentiment_payload(),
            valuation={"dcf_intrinsic_value_per_share": 120.0},
            technical=technical_payload(),
            risk={"risk_rating": "moderate"},
            narrative=narrative,
        )

    def test_narrative_is_rendered_and_attributed(self, raw_data):
        report = self.render(raw_data, "Test Co looks fairly valued today.")
        assert "## Summary" in report
        assert "Test Co looks fairly valued today." in report
        # The reader must be able to tell which part of the report is written.
        assert "Written by an AI model" in report

    def test_it_leads_the_report(self, raw_data):
        report = self.render(raw_data, "The summary.")
        assert report.index("## Summary") < report.index("## Executive Summary")

    def test_absent_narrative_leaves_no_trace(self, raw_data):
        report = self.render(raw_data, None)
        assert "## Summary" not in report
        assert "## Executive Summary" in report

        # No blank-line gap where the section would have been. Scoped to that
        # junction: the disclaimer has its own leading rule and blank line.
        header_end = report.index("**Current Price:**")
        gap = report[header_end:report.index("## Executive Summary")]
        assert "\n\n\n" not in gap

    def test_the_rest_of_the_report_is_unchanged_either_way(self, raw_data):
        with_narrative = self.render(raw_data, "The summary.")
        without = self.render(raw_data, None)
        marker = "## Executive Summary"
        assert with_narrative[with_narrative.index(marker):] == without[without.index(marker):]
