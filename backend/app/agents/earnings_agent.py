"""
Earnings Agent
==============
Summarises the earnings calendar around an analysis.

A recommendation issued three days before results is a different thing from one
issued three days after: the numbers the whole model rests on are about to be
replaced. The report says so, and the recommendation engine treats an imminent
report as a reason for less confidence, not more.
"""

import logging
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.earnings")


class EarningsAgent:
    """Extracts the next earnings date and the recent surprise record."""

    # Within this many days the result is close enough to matter to a reader.
    IMMINENT_DAYS = 14
    # How many past reports feed the beat rate.
    HISTORY_LIMIT = 8

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def run(self, raw_data: dict, today: Optional[date] = None) -> dict[str, Any]:
        """Summarise upcoming and recent earnings."""
        entries = raw_data.get("earnings") or []
        if not isinstance(entries, list) or not entries:
            return {"available": False, "note": "No earnings calendar data was available."}

        today = today or date.today()

        upcoming: list[tuple[date, dict]] = []
        reported: list[tuple[date, dict]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            when = self._parse_date(entry.get("date"))
            if when is None:
                continue
            # A row with no actual EPS has not happened yet.
            if entry.get("epsActual") is None and when >= today:
                upcoming.append((when, entry))
            elif entry.get("epsActual") is not None:
                reported.append((when, entry))

        upcoming.sort(key=lambda pair: pair[0])
        reported.sort(key=lambda pair: pair[0], reverse=True)

        next_date, next_entry = upcoming[0] if upcoming else (None, {})
        days_until = (next_date - today).days if next_date else None

        surprises = []
        beats = 0
        for when, entry in reported[: self.HISTORY_LIMIT]:
            actual = self._as_float(entry.get("epsActual"))
            estimated = self._as_float(entry.get("epsEstimated"))
            surprise_pct = None
            if actual is not None and estimated:
                surprise_pct = round((actual - estimated) / abs(estimated), 4)
                if actual > estimated:
                    beats += 1
            surprises.append(
                {
                    "date": when.isoformat(),
                    "eps_actual": actual,
                    "eps_estimated": estimated,
                    "surprise_pct": surprise_pct,
                }
            )

        scored = [s for s in surprises if s["surprise_pct"] is not None]
        result = {
            "available": True,
            "next_date": next_date.isoformat() if next_date else None,
            "days_until": days_until,
            "is_imminent": days_until is not None and 0 <= days_until <= self.IMMINENT_DAYS,
            "eps_estimate": self._as_float(next_entry.get("epsEstimated")),
            "revenue_estimate": self._as_float(next_entry.get("revenueEstimated")),
            "recent_surprises": surprises,
            "beat_rate": round(beats / len(scored), 3) if scored else None,
            "reports_assessed": len(scored),
        }

        logger.info(
            "Earnings summary: next=%s (%s days), beat rate %s over %d reports",
            result["next_date"], days_until, result["beat_rate"], len(scored),
        )
        return result
