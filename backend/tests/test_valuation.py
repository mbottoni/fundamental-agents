"""
Tests for the DCF valuation agent.

These exercise the model arithmetic directly — no HTTP, no database — so the
numbers can be checked against a hand-computed DCF.
"""

import pytest

from app.agents.valuation_agent import ValuationAgent


def build_raw_data(
    *,
    fcf: list[float] | None = None,
    interest_expense: float = 0.0,
    total_debt: float = 0.0,
    cash: float = 0.0,
    market_cap: float = 1_000_000_000.0,
    beta: float = 1.0,
    shares: float = 10_000_000.0,
    pre_tax_income: float = 100_000_000.0,
    tax_expense: float = 21_000_000.0,
) -> dict:
    """Build a minimal raw_data payload shaped like the data gathering agent's."""
    fcf = fcf if fcf is not None else [100_000_000.0] * 5
    return {
        "ticker": "TEST",
        "profile": {"beta": beta, "marketCap": market_cap},
        "financials": {
            "income_statement": [
                {
                    "interestExpense": interest_expense,
                    "incomeBeforeTax": pre_tax_income,
                    "incomeTaxExpense": tax_expense,
                    "weightedAverageShsOutDil": shares,
                }
                for _ in range(5)
            ],
            "balance_sheet": [
                {
                    "totalDebt": total_debt,
                    "cashAndShortTermInvestments": cash,
                }
            ],
            "cash_flow": [{"freeCashFlow": v} for v in fcf],
        },
    }


class TestEquityBridge:
    """Discounting at WACC yields enterprise value; net debt must come out."""

    def test_net_debt_is_subtracted_from_enterprise_value(self):
        """
        Holding the discount rate fixed, net debt reduces value per share by
        exactly net-debt-per-share. This is the bug the old model had: it
        divided enterprise value straight by the share count.
        """
        agent = ValuationAgent()
        shares = 10_000_000.0
        net_debt = 500_000_000.0

        debt_free, _ = agent._value_per_share(100_000_000.0, 0.05, 0.08, 0.025, 0.0, shares)
        leveraged, _ = agent._value_per_share(100_000_000.0, 0.05, 0.08, 0.025, net_debt, shares)

        assert leveraged < debt_free
        assert debt_free - leveraged == pytest.approx(net_debt / shares, rel=1e-9)

    def test_cash_is_added_back(self):
        agent = ValuationAgent()
        no_cash = agent.run(build_raw_data(total_debt=100_000_000, cash=0))
        with_cash = agent.run(build_raw_data(total_debt=100_000_000, cash=100_000_000))

        assert with_cash["dcf_intrinsic_value_per_share"] > no_cash["dcf_intrinsic_value_per_share"]
        assert no_cash["net_debt"] == 100_000_000
        assert with_cash["net_debt"] == 0

    def test_bridge_is_internally_consistent(self):
        result = ValuationAgent().run(
            build_raw_data(total_debt=250_000_000, cash=50_000_000)
        )
        expected_equity = result["enterprise_value"] - result["net_debt"]
        assert result["equity_value"] == pytest.approx(expected_equity, rel=1e-6)
        assert result["dcf_intrinsic_value_per_share"] == pytest.approx(
            result["equity_value"] / result["shares_outstanding"], rel=1e-3
        )

    def test_negative_equity_value_returns_unavailable(self):
        """Debt far exceeding enterprise value must not yield a negative price target."""
        result = ValuationAgent().run(
            build_raw_data(fcf=[10_000_000.0] * 5, total_debt=100_000_000_000, cash=0)
        )
        assert result["status"] == "unavailable"
        assert result["dcf_intrinsic_value_per_share"] is None


class TestUnleveredCashFlow:
    def test_interest_is_added_back_after_tax(self):
        """FCFF adds back after-tax interest, since FCF is already net of it."""
        agent = ValuationAgent()
        result = agent.run(
            build_raw_data(
                fcf=[100_000_000.0] * 5,
                interest_expense=10_000_000.0,
                pre_tax_income=100_000_000.0,
                tax_expense=21_000_000.0,
            )
        )
        # 100M FCF + 10M interest x (1 - 0.21) = 107.9M
        assert result["latest_fcff"] == pytest.approx(107_900_000, rel=1e-6)


class TestGuardRails:
    def test_negative_free_cash_flow_is_not_valued(self):
        result = ValuationAgent().run(build_raw_data(fcf=[-50_000_000.0] * 5))
        assert result["status"] == "unavailable"
        assert result["dcf_intrinsic_value_per_share"] is None
        assert "negative" in result["error"].lower()

    def test_wacc_is_floored_above_terminal_growth(self):
        """A low-beta, debt-heavy company must not produce a near-zero discount rate."""
        agent = ValuationAgent()
        result = agent.run(build_raw_data(beta=0.05, total_debt=10_000, cash=0))
        assert result["wacc"] >= agent.perpetual_growth_rate + agent.MIN_SPREAD_OVER_GROWTH
        assert result["wacc"] >= agent.MIN_WACC

    def test_wacc_is_capped(self):
        agent = ValuationAgent()
        result = agent.run(build_raw_data(beta=12.0))
        assert result["wacc"] <= agent.MAX_WACC

    def test_growth_rate_is_clamped(self):
        agent = ValuationAgent()
        explosive = agent.run(build_raw_data(fcf=[1_000_000_000.0, 10_000_000.0, 1_000_000.0]))
        assert explosive["fcf_growth_rate"] <= agent.MAX_GROWTH

        collapsing = agent.run(build_raw_data(fcf=[1_000_000.0, 100_000_000.0, 500_000_000.0]))
        assert collapsing["fcf_growth_rate"] >= agent.MIN_GROWTH

    def test_missing_shares_outstanding_is_unavailable(self):
        raw = build_raw_data()
        for statement in raw["financials"]["income_statement"]:
            statement.pop("weightedAverageShsOutDil")
        result = ValuationAgent().run(raw)
        assert result["status"] == "unavailable"

    def test_missing_profile_is_unavailable(self):
        raw = build_raw_data()
        raw["profile"] = {}
        result = ValuationAgent().run(raw)
        assert result["status"] == "unavailable"
        assert result["dcf_intrinsic_value_per_share"] is None


class TestGrowthEstimation:
    def test_cagr_is_preferred_over_arithmetic_mean(self):
        """
        A recovery year followed by flat growth: the arithmetic mean of YoY rates
        would be badly skewed, the CAGR should not be.
        """
        agent = ValuationAgent()
        # Oldest → newest: 10, 100, 105, 110, 115 (newest first below)
        history = [115.0, 110.0, 105.0, 100.0, 10.0]
        growth, basis = agent._estimate_growth(history)
        assert "CAGR" in basis
        # CAGR over 4 periods from 10 → 115 is ~84%, clamped to the cap.
        assert growth == agent.MAX_GROWTH

    def test_falls_back_to_default_without_history(self):
        agent = ValuationAgent()
        growth, basis = agent._estimate_growth([100.0])
        assert growth == agent.DEFAULT_FCF_GROWTH
        assert "default" in basis

    def test_growth_fades_toward_terminal_rate(self):
        agent = ValuationAgent()
        projected = agent._project(100.0, 0.20, 0.025)
        assert len(projected) == agent.PROJECTION_YEARS
        first_year_growth = projected[0] / 100.0 - 1
        last_year_growth = projected[-1] / projected[-2] - 1
        assert first_year_growth == pytest.approx(0.20, rel=1e-6)
        assert last_year_growth == pytest.approx(0.025, rel=1e-6)


class TestSensitivity:
    def test_grid_brackets_the_point_estimate(self):
        result = ValuationAgent().run(build_raw_data())
        sensitivity = result["sensitivity"]
        value = result["dcf_intrinsic_value_per_share"]

        assert sensitivity["low"] <= value <= sensitivity["high"]
        assert len(sensitivity["grid"]) == len(sensitivity["wacc_values"])
        assert all(len(row) == len(sensitivity["terminal_growth_values"]) for row in sensitivity["grid"])

    def test_higher_wacc_lowers_value(self):
        agent = ValuationAgent()
        low_wacc, _ = agent._value_per_share(100.0, 0.05, 0.08, 0.025, 0.0, 10.0)
        high_wacc, _ = agent._value_per_share(100.0, 0.05, 0.12, 0.025, 0.0, 10.0)
        assert high_wacc < low_wacc

    def test_incoherent_assumptions_produce_no_value(self):
        agent = ValuationAgent()
        value, _ = agent._value_per_share(100.0, 0.05, 0.03, 0.035, 0.0, 10.0)
        assert value is None


class TestBackwardCompatibility:
    """Keys the orchestrator and report agent already depend on."""

    def test_success_payload_keys(self):
        result = ValuationAgent().run(build_raw_data())
        for key in ("dcf_intrinsic_value_per_share", "wacc", "latest_fcf"):
            assert key in result

    def test_failure_payload_keys(self):
        result = ValuationAgent().run(build_raw_data(fcf=[]))
        assert result["dcf_intrinsic_value_per_share"] is None
        assert "error" in result
