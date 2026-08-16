"""
Valuation Agent
===============
Two‑stage discounted cash flow (DCF) valuation on an *unlevered* basis:

    FCFF        = Free Cash Flow + after‑tax interest expense
    Enterprise  = Σ PV(projected FCFF) + PV(terminal value)      [discounted at WACC]
    Equity      = Enterprise − total debt + cash & equivalents
    Per share   = Equity / diluted shares outstanding

The equity bridge is not optional: discounting at WACC yields an *enterprise*
value, so net debt has to be removed before dividing by the share count.
Skipping it overstates every leveraged company by roughly net‑debt‑per‑share.

Because the output is dominated by two assumptions (WACC and terminal growth),
every run also produces a sensitivity grid instead of a single point estimate.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.valuation")


class ValuationAgent:
    """Performs a two‑stage FCFF discounted cash flow valuation."""

    # ── model assumptions ─────────────────────────────────────
    DEFAULT_RISK_FREE_RATE = 0.04
    DEFAULT_MARKET_RETURN = 0.08
    DEFAULT_PERPETUAL_GROWTH_RATE = 0.025
    DEFAULT_TAX_RATE = 0.21
    DEFAULT_FCF_GROWTH = 0.05
    PROJECTION_YEARS = 5

    # ── guard rails ───────────────────────────────────────────
    # A discount rate that sits close to the perpetual growth rate makes the
    # terminal value explode, so the spread is floored rather than merely
    # checked for sign.
    MIN_WACC = 0.06
    MAX_WACC = 0.20
    MIN_SPREAD_OVER_GROWTH = 0.03
    MAX_GROWTH = 0.25
    MIN_GROWTH = -0.15
    MAX_EFFECTIVE_TAX_RATE = 0.50
    # Flag (but still report) valuations that are almost entirely terminal value.
    TERMINAL_VALUE_WARN_SHARE = 0.85

    # ── sensitivity grid ──────────────────────────────────────
    WACC_DELTAS = (-0.02, -0.01, 0.0, 0.01, 0.02)
    TERMINAL_GROWTH_VALUES = (0.015, 0.020, 0.025, 0.030, 0.035)

    def __init__(
        self,
        risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
        market_return: float = DEFAULT_MARKET_RETURN,
        perpetual_growth_rate: float = DEFAULT_PERPETUAL_GROWTH_RATE,
    ) -> None:
        self.risk_free_rate = risk_free_rate
        self.market_return = market_return
        self.perpetual_growth_rate = perpetual_growth_rate

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _first(data: list[dict], *keys: str) -> Any:
        """Return the first non‑null value among *keys* on the latest statement."""
        if not data:
            return None
        latest = data[0] or {}
        for key in keys:
            value = latest.get(key)
            if value is not None:
                return value
        return None

    def _effective_tax_rate(self, income_statement: list[dict]) -> float:
        """Effective tax rate from the latest income statement, clamped to a sane band."""
        tax_expense = self._first(income_statement, "incomeTaxExpense")
        pre_tax_income = self._first(income_statement, "incomeBeforeTax")
        try:
            if tax_expense is not None and pre_tax_income:
                rate = float(tax_expense) / float(pre_tax_income)
                if 0.0 <= rate <= self.MAX_EFFECTIVE_TAX_RATE:
                    return rate
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return self.DEFAULT_TAX_RATE

    # ── cost of capital ───────────────────────────────────────

    def _calculate_wacc(self, raw_data: dict) -> tuple[Optional[float], list[str]]:
        """
        Weighted Average Cost of Capital.

        Returns (wacc, warnings). The rate is clamped into [MIN_WACC, MAX_WACC]
        and forced to sit at least MIN_SPREAD_OVER_GROWTH above the perpetual
        growth rate so the Gordon terminal value stays finite and sane.
        """
        warnings: list[str] = []
        try:
            profile = raw_data.get("profile") or {}
            financials = raw_data.get("financials") or {}
            balance_sheet = financials.get("balance_sheet") or []
            income_statement = financials.get("income_statement") or []

            beta = profile.get("beta")
            # FMP /stable API renamed mktCap → marketCap
            market_cap = profile.get("marketCap") or profile.get("mktCap")

            if beta is None or not market_cap:
                logger.warning("Missing beta or market cap for WACC calculation")
                return None, ["Beta or market capitalisation unavailable."]

            total_debt = self._first(balance_sheet, "totalDebt") or 0.0
            interest_expense = self._first(income_statement, "interestExpense") or 0.0
            effective_tax_rate = self._effective_tax_rate(income_statement)

            # Cost of equity (CAPM)
            cost_of_equity = self.risk_free_rate + float(beta) * (
                self.market_return - self.risk_free_rate
            )

            # Cost of debt, after tax
            cost_of_debt = (float(interest_expense) / float(total_debt)) if total_debt else 0.0
            # A nonsensical implied rate usually means FMP reported interest expense
            # for a different scope than the debt balance.
            if cost_of_debt > 0.25 or cost_of_debt < 0:
                warnings.append("Implied cost of debt out of range; used the risk‑free rate instead.")
                cost_of_debt = self.risk_free_rate
            after_tax_cost_of_debt = cost_of_debt * (1 - effective_tax_rate)

            total_capital = float(market_cap) + float(total_debt)
            if total_capital <= 0:
                return None, ["Total capital is zero or negative."]

            wacc = (
                (float(market_cap) / total_capital) * cost_of_equity
                + (float(total_debt) / total_capital) * after_tax_cost_of_debt
            )

            floor = max(self.MIN_WACC, self.perpetual_growth_rate + self.MIN_SPREAD_OVER_GROWTH)
            if wacc < floor:
                warnings.append(
                    f"Computed WACC of {wacc:.2%} was raised to the {floor:.2%} floor "
                    "to keep the terminal value meaningful."
                )
                wacc = floor
            elif wacc > self.MAX_WACC:
                warnings.append(f"Computed WACC of {wacc:.2%} was capped at {self.MAX_WACC:.2%}.")
                wacc = self.MAX_WACC

            logger.info("WACC calculated: %.4f", wacc)
            return wacc, warnings

        except (TypeError, ValueError, ZeroDivisionError, IndexError) as e:
            logger.error("Error calculating WACC: %s", e)
            return None, [f"WACC calculation failed: {e}"]

    # ── free cash flow ────────────────────────────────────────

    def _fcff_history(
        self, cash_flow: list[dict], income_statement: list[dict], tax_rate: float
    ) -> list[float]:
        """
        Unlevered free cash flow, newest first.

        FMP's `freeCashFlow` is operating cash flow less capex, and operating
        cash flow is already net of interest paid — so interest is added back,
        after tax, to get a cash flow that belongs to *all* capital providers
        and can legitimately be discounted at WACC.
        """
        history: list[float] = []
        for index, period in enumerate(cash_flow[: self.PROJECTION_YEARS]):
            fcf = (period or {}).get("freeCashFlow")
            if fcf is None:
                continue
            try:
                interest = 0.0
                if index < len(income_statement):
                    interest = float((income_statement[index] or {}).get("interestExpense") or 0.0)
                history.append(float(fcf) + interest * (1 - tax_rate))
            except (TypeError, ValueError):
                continue
        return history

    def _estimate_growth(self, fcff_history: list[float]) -> tuple[float, str]:
        """
        Estimate a forward growth rate from historical unlevered cash flow.

        Prefers a CAGR across the full window (stable, insensitive to a single
        outlier year); falls back to the median year‑over‑year rate when the
        endpoints make a CAGR meaningless, then to a fixed default.
        """
        usable = [v for v in fcff_history if v is not None]

        if len(usable) >= 3 and usable[0] > 0 and usable[-1] > 0:
            years = len(usable) - 1
            cagr = (usable[0] / usable[-1]) ** (1 / years) - 1
            return self._clamp_growth(cagr), "CAGR of historical unlevered FCF"

        yoy = [
            (usable[i] - usable[i + 1]) / abs(usable[i + 1])
            for i in range(len(usable) - 1)
            if usable[i + 1] != 0
        ]
        if yoy:
            ordered = sorted(yoy)
            mid = len(ordered) // 2
            median = (
                ordered[mid]
                if len(ordered) % 2
                else (ordered[mid - 1] + ordered[mid]) / 2
            )
            return self._clamp_growth(median), "median year‑over‑year growth"

        return self.DEFAULT_FCF_GROWTH, "default assumption (insufficient history)"

    def _clamp_growth(self, growth: float) -> float:
        return max(self.MIN_GROWTH, min(growth, self.MAX_GROWTH))

    def _project(self, base_fcff: float, growth: float, terminal_growth: float) -> list[float]:
        """
        Project FCFF, fading the growth rate linearly from the estimated rate in
        year 1 down to the perpetual rate in the final year. A company does not
        sustain 25% growth for five straight years and then drop to 2.5%.
        """
        projected: list[float] = []
        current = base_fcff
        for year in range(self.PROJECTION_YEARS):
            fade = year / max(self.PROJECTION_YEARS - 1, 1)
            year_growth = growth + (terminal_growth - growth) * fade
            current = current * (1 + year_growth)
            projected.append(current)
        return projected

    # ── valuation ─────────────────────────────────────────────

    def _value_per_share(
        self,
        base_fcff: float,
        growth: float,
        wacc: float,
        terminal_growth: float,
        net_debt: float,
        shares: float,
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Run the model for one (WACC, terminal growth) pair.

        Returns (value per share, terminal value share of enterprise value);
        both None when the assumptions are incoherent.
        """
        if wacc - terminal_growth < self.MIN_SPREAD_OVER_GROWTH or shares <= 0:
            return None, None

        projected = self._project(base_fcff, growth, terminal_growth)

        pv_explicit = sum(
            fcff / ((1 + wacc) ** (year + 1)) for year, fcff in enumerate(projected)
        )
        terminal_value = projected[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal = terminal_value / ((1 + wacc) ** len(projected))

        enterprise_value = pv_explicit + pv_terminal
        equity_value = enterprise_value - net_debt
        if equity_value <= 0:
            return None, None

        terminal_share = pv_terminal / enterprise_value if enterprise_value else None
        return equity_value / shares, terminal_share

    def _sensitivity(
        self,
        base_fcff: float,
        growth: float,
        wacc: float,
        net_debt: float,
        shares: float,
    ) -> dict[str, Any]:
        """Value per share across a WACC × terminal‑growth grid."""
        wacc_values = [round(wacc + delta, 4) for delta in self.WACC_DELTAS if wacc + delta > 0]
        grid: list[list[Optional[float]]] = []
        finite: list[float] = []

        for w in wacc_values:
            row: list[Optional[float]] = []
            for g in self.TERMINAL_GROWTH_VALUES:
                value, _ = self._value_per_share(base_fcff, growth, w, g, net_debt, shares)
                value = round(value, 2) if value is not None else None
                row.append(value)
                if value is not None:
                    finite.append(value)
            grid.append(row)

        return {
            "wacc_values": wacc_values,
            "terminal_growth_values": list(self.TERMINAL_GROWTH_VALUES),
            "grid": grid,
            "low": round(min(finite), 2) if finite else None,
            "high": round(max(finite), 2) if finite else None,
        }

    # ── main entry point ──────────────────────────────────────

    def _unavailable(self, reason: str, **extra: Any) -> dict[str, Any]:
        logger.warning("DCF valuation unavailable: %s", reason)
        return {
            "dcf_intrinsic_value_per_share": None,
            "status": "unavailable",
            "error": reason,
            **extra,
        }

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Run the full DCF valuation."""
        logger.info("Starting DCF valuation")

        financials = raw_data.get("financials") or {}
        income_statement = financials.get("income_statement") or []
        balance_sheet = financials.get("balance_sheet") or []
        cash_flow = financials.get("cash_flow") or []
        profile = raw_data.get("profile") or {}

        wacc, warnings = self._calculate_wacc(raw_data)
        if wacc is None:
            return self._unavailable(
                "Could not calculate WACC: " + (warnings[0] if warnings else "missing inputs.")
            )

        tax_rate = self._effective_tax_rate(income_statement)
        fcff_history = self._fcff_history(cash_flow, income_statement, tax_rate)
        if not fcff_history:
            return self._unavailable("No free cash flow data available.", wacc=round(wacc, 4))

        base_fcff = fcff_history[0]
        if base_fcff <= 0:
            # Projecting a negative cash flow forward produces a negative
            # intrinsic value and a spurious "strong sell". A DCF simply does
            # not apply to a business that is currently burning cash.
            return self._unavailable(
                "Latest unlevered free cash flow is negative — a DCF is not meaningful "
                "for a cash‑burning business. Rely on the multiples and growth sections instead.",
                wacc=round(wacc, 4),
                latest_fcf=self._first(cash_flow, "freeCashFlow"),
            )

        growth, growth_basis = self._estimate_growth(fcff_history)

        # ── equity bridge ────────────────────────────────────
        total_debt = float(self._first(balance_sheet, "totalDebt") or 0.0)
        cash = float(
            self._first(balance_sheet, "cashAndShortTermInvestments", "cashAndCashEquivalents")
            or 0.0
        )
        net_debt = total_debt - cash

        # FMP /stable removed sharesOutstanding from the profile; fall back to
        # the diluted share count on the latest income statement.
        shares = (
            profile.get("sharesOutstanding")
            or self._first(income_statement, "weightedAverageShsOutDil", "weightedAverageShsOut")
        )
        if not shares:
            return self._unavailable("Shares outstanding not available.", wacc=round(wacc, 4))
        shares = float(shares)

        value_per_share, terminal_share = self._value_per_share(
            base_fcff, growth, wacc, self.perpetual_growth_rate, net_debt, shares,
        )
        if value_per_share is None:
            return self._unavailable(
                "Enterprise value does not cover net debt — the implied equity value is negative.",
                wacc=round(wacc, 4),
                net_debt=net_debt,
            )

        if terminal_share is not None and terminal_share > self.TERMINAL_VALUE_WARN_SHARE:
            warnings.append(
                f"{terminal_share:.0%} of the valuation comes from the terminal value, "
                "so the result is highly sensitive to the perpetual growth assumption."
            )

        projected = self._project(base_fcff, growth, self.perpetual_growth_rate)
        sensitivity = self._sensitivity(base_fcff, growth, wacc, net_debt, shares)
        equity_value = value_per_share * shares
        enterprise_value = equity_value + net_debt

        logger.info(
            "DCF valuation complete: %.2f per share (WACC %.2f%%, growth %.2f%%, range %s–%s)",
            value_per_share, wacc * 100, growth * 100, sensitivity["low"], sensitivity["high"],
        )

        return {
            "dcf_intrinsic_value_per_share": round(value_per_share, 2),
            "status": "ok",
            "method": "two‑stage FCFF DCF with net‑debt bridge",
            "wacc": round(wacc, 4),
            "terminal_growth_rate": self.perpetual_growth_rate,
            "fcf_growth_rate": round(growth, 4),
            "fcf_growth_basis": growth_basis,
            "latest_fcf": self._first(cash_flow, "freeCashFlow"),
            "latest_fcff": round(base_fcff, 2),
            "projected_fcff": [round(v, 2) for v in projected],
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value, 2),
            "total_debt": total_debt,
            "cash": cash,
            "net_debt": net_debt,
            "shares_outstanding": shares,
            "terminal_value_share": round(terminal_share, 4) if terminal_share else None,
            "sensitivity": sensitivity,
            "warnings": warnings,
        }
