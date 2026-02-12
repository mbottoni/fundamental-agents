import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.valuation")


class ValuationAgent:
    """Performs DCF valuation using WACC and projected free cash flows."""

    # These are configurable defaults, could be moved to Settings if needed.
    DEFAULT_RISK_FREE_RATE = 0.04
    DEFAULT_MARKET_RETURN = 0.08
    DEFAULT_PERPETUAL_GROWTH_RATE = 0.025
    DEFAULT_TAX_RATE = 0.21
    DEFAULT_FCF_GROWTH = 0.05
    PROJECTION_YEARS = 5

    def __init__(
        self,
        risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
        market_return: float = DEFAULT_MARKET_RETURN,
        perpetual_growth_rate: float = DEFAULT_PERPETUAL_GROWTH_RATE,
    ) -> None:
        self.risk_free_rate = risk_free_rate
        self.market_return = market_return
        self.perpetual_growth_rate = perpetual_growth_rate

    def _calculate_wacc(self, raw_data: dict) -> Optional[float]:
        """Calculate Weighted Average Cost of Capital."""
        try:
            profile = raw_data.get("profile") or {}
            financials = raw_data.get("financials") or {}

            beta = profile.get("beta")
            # FMP /stable API renamed mktCap → marketCap
            market_cap = profile.get("marketCap") or profile.get("mktCap")

            balance_sheet = (financials.get("balance_sheet") or [{}])[0]
            income_statement = (financials.get("income_statement") or [{}])[0]

            total_debt = balance_sheet.get("totalDebt")
            interest_expense = income_statement.get("interestExpense")
            income_before_tax = income_statement.get("incomeBeforeTax")

            if not all([beta, market_cap, total_debt is not None, interest_expense is not None]):
                logger.warning("Missing data for WACC calculation")
                return None

            # Cost of Equity (CAPM)
            cost_of_equity = self.risk_free_rate + beta * (self.market_return - self.risk_free_rate)

            # Cost of Debt
            if income_before_tax and income_before_tax != 0:
                tax_expense = income_statement.get("incomeTaxExpense", 0) or 0
                effective_tax_rate = tax_expense / income_before_tax
            else:
                effective_tax_rate = self.DEFAULT_TAX_RATE

            cost_of_debt = (interest_expense / total_debt) if total_debt else 0
            after_tax_cost_of_debt = cost_of_debt * (1 - effective_tax_rate)

            # WACC
            total_capital = market_cap + total_debt
            if total_capital == 0:
                return None

            wacc = (
                (market_cap / total_capital) * cost_of_equity
                + (total_debt / total_capital) * after_tax_cost_of_debt
            )

            logger.info("WACC calculated: %.4f", wacc)
            return wacc

        except (TypeError, ZeroDivisionError, IndexError) as e:
            logger.error("Error calculating WACC: %s", e)
            return None

    def _project_free_cash_flow(
        self, cash_flow_data: list[dict],
    ) -> tuple[Optional[list[float]], Optional[float]]:
        """Project free cash flows based on historical growth rates."""
        try:
            latest_fcf = cash_flow_data[0].get("freeCashFlow")
            if not latest_fcf:
                logger.warning("No free cash flow data available")
                return None, None

            # Calculate historical average growth rate
            fcf_history = [
                cf.get("freeCashFlow", 0)
                for cf in cash_flow_data[:5]
                if cf.get("freeCashFlow")
            ]

            growth_rates = [
                (fcf_history[i] - fcf_history[i + 1]) / abs(fcf_history[i + 1])
                for i in range(len(fcf_history) - 1)
                if fcf_history[i + 1] != 0
            ]

            avg_growth_rate = (
                sum(growth_rates) / len(growth_rates)
                if growth_rates
                else self.DEFAULT_FCF_GROWTH
            )

            # Cap growth rate to reasonable bounds
            avg_growth_rate = max(-0.20, min(avg_growth_rate, 0.30))

            projected_fcf = [
                latest_fcf * ((1 + avg_growth_rate) ** year)
                for year in range(1, self.PROJECTION_YEARS + 1)
            ]

            logger.info("Projected FCF with %.2f%% growth rate", avg_growth_rate * 100)
            return projected_fcf, latest_fcf

        except (IndexError, TypeError, ZeroDivisionError) as e:
            logger.error("Error projecting FCF: %s", e)
            return None, None

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Run the full DCF valuation analysis."""
        logger.info("Starting DCF valuation")

        wacc = self._calculate_wacc(raw_data)
        if wacc is None:
            return {"dcf_intrinsic_value_per_share": None, "error": "Could not calculate WACC."}

        cash_flow_data = raw_data.get("financials", {}).get("cash_flow", [])
        projected_fcf, latest_fcf = self._project_free_cash_flow(cash_flow_data)
        if projected_fcf is None:
            return {"dcf_intrinsic_value_per_share": None, "error": "Could not project Free Cash Flow."}

        # Guard against WACC <= perpetual growth rate (invalid terminal value)
        if wacc <= self.perpetual_growth_rate:
            return {
                "dcf_intrinsic_value_per_share": None,
                "error": "WACC is less than or equal to perpetual growth rate.",
            }

        # Discount projected FCF
        dcf_sum = sum(
            fcf / ((1 + wacc) ** (i + 1))
            for i, fcf in enumerate(projected_fcf)
        )

        # Terminal value (Gordon Growth Model)
        terminal_value = (
            projected_fcf[-1] * (1 + self.perpetual_growth_rate)
        ) / (wacc - self.perpetual_growth_rate)
        discounted_terminal_value = terminal_value / ((1 + wacc) ** len(projected_fcf))

        # Intrinsic value
        intrinsic_value = dcf_sum + discounted_terminal_value

        # FMP /stable API removed sharesOutstanding from profile;
        # fall back to weightedAverageShsOut from the latest income statement.
        shares_outstanding = (raw_data.get("profile") or {}).get("sharesOutstanding")
        if not shares_outstanding:
            income_stmts = raw_data.get("financials", {}).get("income_statement", [])
            if income_stmts:
                shares_outstanding = income_stmts[0].get("weightedAverageShsOut")
        if not shares_outstanding:
            return {"dcf_intrinsic_value_per_share": None, "error": "Shares outstanding not available."}

        intrinsic_value_per_share = intrinsic_value / shares_outstanding

        logger.info("DCF valuation complete: intrinsic value per share = $%.2f", intrinsic_value_per_share)

        return {
            "dcf_intrinsic_value_per_share": round(intrinsic_value_per_share, 2),
            "wacc": round(wacc, 4),
            "latest_fcf": latest_fcf,
        }
