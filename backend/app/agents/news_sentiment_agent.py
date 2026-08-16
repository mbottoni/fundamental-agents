"""
News Sentiment Agent
====================
Scores recent coverage of a company with VADER, adapted for financial text.

Three adjustments make the score mean something:

* **A finance lexicon.** VADER is tuned on social media, where "beat" is
  violence and "miss" is longing. In market coverage they are the two most
  informative words there are, so the lexicon is extended with the vocabulary
  of earnings and ratings.
* **Relevance filtering.** Even a well-formed query returns articles that
  merely mention the company in passing, so an article has to name the company
  or its ticker to count.
* **Recency weighting.** A downgrade this morning matters more than a puff
  piece from three weeks ago; article weight decays with a one-week half-life.
"""

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

logger = logging.getLogger("stock_analyzer.agents.news_sentiment")


# Domain terms VADER either scores backwards or does not know. Values are on
# VADER's own -4..+4 scale.
FINANCE_LEXICON: dict[str, float] = {
    # Earnings and guidance
    "beat": 2.6, "beats": 2.6, "outperform": 2.4, "outperformed": 2.4,
    "exceeded": 2.4, "exceeds": 2.4, "topped": 1.9, "raised": 1.8,
    "raises": 1.8, "upbeat": 2.0, "record": 1.6, "profitable": 2.2,
    "miss": -2.4, "misses": -2.4, "missed": -2.4, "shortfall": -2.4,
    "underperform": -2.4, "underperformed": -2.4, "disappointing": -2.4,
    "lowered": -1.8, "lowers": -1.8, "slashed": -2.6, "warns": -2.2,
    "warning": -2.0,
    # Analyst actions
    "upgrade": 2.6, "upgraded": 2.6, "upgrades": 2.6, "bullish": 2.6,
    "overweight": 1.4, "buy": 1.5,
    "downgrade": -2.6, "downgraded": -2.6, "downgrades": -2.6, "bearish": -2.6,
    "underweight": -1.4,
    # Price action
    "surge": 2.5, "surged": 2.5, "surges": 2.5, "soared": 2.7, "soars": 2.7,
    "rally": 2.2, "rallied": 2.2, "jumped": 1.9, "climbed": 1.5, "gains": 1.6,
    "plunge": -2.8, "plunged": -2.8, "plunges": -2.8, "tumbled": -2.6,
    "tumbles": -2.6, "slump": -2.5, "slumped": -2.5, "sank": -2.3,
    "selloff": -2.4, "plummeted": -2.9, "slid": -1.7, "losses": -1.8,
    # Corporate events
    "buyback": 1.8, "dividend": 1.2, "acquisition": 0.8, "expansion": 1.4,
    "partnership": 1.2, "approval": 1.8, "breakthrough": 2.2,
    "bankruptcy": -3.4, "insolvency": -3.4, "default": -2.6, "delisting": -3.0,
    "fraud": -3.4, "probe": -2.0, "investigation": -1.9, "lawsuit": -2.0,
    "subpoena": -2.2, "recall": -2.1, "layoffs": -2.2, "restructuring": -1.2,
    "halted": -2.0, "downturn": -2.0, "headwinds": -1.6, "tailwinds": 1.6,
}

# Words to drop from a company name before matching it in article text.
COMPANY_SUFFIXES = {
    "inc", "inc.", "corp", "corp.", "corporation", "co", "co.", "company",
    "ltd", "ltd.", "limited", "plc", "llc", "lp", "nv", "sa", "ag", "holdings",
    "holding", "group", "the", "&",
}


class NewsSentimentAgent:
    """Analyzes sentiment from news articles using a finance-tuned VADER."""

    POSITIVE_THRESHOLD = 0.05
    NEGATIVE_THRESHOLD = -0.05

    # Article weight halves every this many days.
    RECENCY_HALF_LIFE_DAYS = 7.0
    # Beyond this age an article is ignored entirely.
    MAX_ARTICLE_AGE_DAYS = 45.0
    # Tickers shorter than this are too common in prose to match on.
    MIN_TICKER_MATCH_LENGTH = 3

    def __init__(self) -> None:
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            logger.info("Downloading VADER lexicon...")
            nltk.download("vader_lexicon", quiet=True)
        self.sia = SentimentIntensityAnalyzer()
        self.sia.lexicon.update(FINANCE_LEXICON)

    # ── helpers ───────────────────────────────────────────────

    def analyze_sentiment(self, text: str) -> Optional[dict[str, float]]:
        """Analyze the sentiment of a given text string."""
        if not text or not text.strip():
            return None
        return self.sia.polarity_scores(text)

    @staticmethod
    def _company_tokens(company_name: Optional[str]) -> set[str]:
        """Distinctive lowercase tokens from a company name."""
        if not company_name:
            return set()
        tokens = re.findall(r"[a-z0-9]+", company_name.lower())
        return {t for t in tokens if t not in COMPANY_SUFFIXES and len(t) > 2}

    def _is_relevant(self, text: str, ticker: Optional[str], tokens: set[str]) -> bool:
        """
        Whether an article is actually about the company.

        Short tickers are not matched at all: a bare "F" or "A" appears in
        ordinary prose constantly, so those symbols have to be recognised by
        company name. Longer tickers are matched case-sensitively, so "IT" or
        "ALL" as words do not count as mentions.

        With nothing to match on, everything is kept rather than discarded.
        """
        usable_ticker = (
            ticker if ticker and len(ticker) >= self.MIN_TICKER_MATCH_LENGTH else None
        )
        if not usable_ticker and not tokens:
            return True

        if usable_ticker and re.search(rf"\b{re.escape(usable_ticker.upper())}\b", text):
            return True

        lowered = text.lower()
        return any(token in lowered for token in tokens)

    def _recency_weight(self, published_at: Optional[str], now: datetime) -> Optional[float]:
        """
        Exponential decay by article age. Undated articles get the weight of
        one half-life rather than being dropped or treated as breaking news.
        """
        if not published_at:
            return 0.5
        try:
            published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return 0.5
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        age_days = (now - published).total_seconds() / 86400
        if age_days > self.MAX_ARTICLE_AGE_DAYS:
            return None
        if age_days < 0:  # clock skew on the provider's side
            age_days = 0.0
        return math.pow(0.5, age_days / self.RECENCY_HALF_LIFE_DAYS)

    @staticmethod
    def _empty_result(reason: str, irrelevant: int = 0, stale: int = 0) -> dict[str, Any]:
        return {
            "average_sentiment_compound": 0.0,
            "positive_articles_count": 0,
            "negative_articles_count": 0,
            "neutral_articles_count": 0,
            "analyzed_articles_count": 0,
            "excluded_irrelevant_count": irrelevant,
            "excluded_stale_count": stale,
            "most_positive_headline": None,
            "most_negative_headline": None,
            "note": reason,
        }

    # ── main entry point ──────────────────────────────────────

    def run(
        self,
        news_data: list[dict[str, Any]],
        ticker: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyze sentiment across a list of news articles."""
        news_data = news_data or []
        logger.info("Analyzing sentiment for %d articles", len(news_data))

        now = datetime.now(timezone.utc)
        tokens = self._company_tokens(company_name)

        scored: list[tuple[float, float, str]] = []  # (compound, weight, title)
        skipped_irrelevant = 0
        skipped_stale = 0

        for article in news_data:
            title = article.get("title") or ""
            description = article.get("description") or ""
            text = f"{title}. {description}".strip()
            if not text or text == ".":
                continue

            if not self._is_relevant(text, ticker, tokens):
                skipped_irrelevant += 1
                continue

            weight = self._recency_weight(article.get("publishedAt"), now)
            if weight is None:
                skipped_stale += 1
                continue

            sentiment = self.analyze_sentiment(text)
            if sentiment:
                scored.append((sentiment["compound"], weight, title))

        if not scored:
            logger.warning(
                "No usable articles for sentiment (%d irrelevant, %d stale)",
                skipped_irrelevant, skipped_stale,
            )
            return self._empty_result(
                "No recent articles about this company were found."
                if news_data
                else "No news articles were returned.",
                irrelevant=skipped_irrelevant,
                stale=skipped_stale,
            )

        total_weight = sum(w for _, w, _ in scored)
        avg_compound = sum(c * w for c, w, _ in scored) / total_weight

        positive = sum(1 for c, _, _ in scored if c > self.POSITIVE_THRESHOLD)
        negative = sum(1 for c, _, _ in scored if c < self.NEGATIVE_THRESHOLD)
        neutral = len(scored) - positive - negative

        ranked = sorted(scored, key=lambda s: s[0])
        result = {
            "average_sentiment_compound": round(avg_compound, 4),
            "positive_articles_count": positive,
            "negative_articles_count": negative,
            "neutral_articles_count": neutral,
            "analyzed_articles_count": len(scored),
            "excluded_irrelevant_count": skipped_irrelevant,
            "excluded_stale_count": skipped_stale,
            "most_positive_headline": ranked[-1][2] if ranked[-1][0] > 0 else None,
            "most_negative_headline": ranked[0][2] if ranked[0][0] < 0 else None,
        }

        logger.info(
            "Sentiment complete: avg=%.4f (recency-weighted), pos=%d, neg=%d, neutral=%d, "
            "excluded=%d",
            avg_compound, positive, negative, neutral, skipped_irrelevant + skipped_stale,
        )
        return result
