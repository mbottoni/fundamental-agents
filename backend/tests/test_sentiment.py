"""
Tests for the news sentiment agent: financial vocabulary, relevance
filtering, and recency weighting.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.agents.news_sentiment_agent import NewsSentimentAgent


def article(title: str, description: str = "", age_days: float = 1.0) -> dict:
    published = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {
        "title": title,
        "description": description,
        "publishedAt": published.isoformat().replace("+00:00", "Z"),
    }


@pytest.fixture(scope="module")
def agent() -> NewsSentimentAgent:
    return NewsSentimentAgent()


class TestFinancialVocabulary:
    def test_earnings_beat_reads_as_positive(self, agent):
        """VADER's stock lexicon scores "beat" as violence."""
        score = agent.analyze_sentiment("Apple beat earnings estimates")
        assert score["compound"] > 0.3

    def test_earnings_miss_reads_as_negative(self, agent):
        score = agent.analyze_sentiment("Apple missed earnings estimates")
        assert score["compound"] < -0.3

    def test_analyst_downgrade_is_negative(self, agent):
        assert agent.analyze_sentiment("Analysts downgrade Apple")["compound"] < -0.3

    def test_analyst_upgrade_is_positive(self, agent):
        assert agent.analyze_sentiment("Analysts upgrade Apple")["compound"] > 0.3

    @pytest.mark.parametrize(
        "headline",
        ["Shares plunge after guidance", "Company files for bankruptcy",
         "Regulator opens fraud probe", "Firm announces layoffs"],
    )
    def test_distress_language_is_negative(self, agent, headline):
        assert agent.analyze_sentiment(headline)["compound"] < 0

    @pytest.mark.parametrize(
        "headline",
        ["Shares surge on results", "Board approves buyback",
         "Revenue exceeded expectations", "Stock rallies to record"],
    )
    def test_strength_language_is_positive(self, agent, headline):
        assert agent.analyze_sentiment(headline)["compound"] > 0


class TestRelevanceFiltering:
    def test_unrelated_articles_are_excluded(self, agent):
        articles = [
            article("Ford Motor Company beats quarterly estimates"),
            article("A guide to the letter F in typography"),
            article("Recipes for a great weekend"),
        ]
        result = agent.run(articles, ticker="F", company_name="Ford Motor Company")

        assert result["analyzed_articles_count"] == 1
        assert result["excluded_irrelevant_count"] == 2

    def test_ticker_mention_alone_is_enough(self, agent):
        result = agent.run(
            [article("AAPL climbs after product launch")],
            ticker="AAPL",
            company_name="Apple Inc.",
        )
        assert result["analyzed_articles_count"] == 1

    def test_corporate_suffixes_do_not_match_everything(self, agent):
        """Matching on "Inc" or "Group" would let any business story through."""
        result = agent.run(
            [article("Some other Inc. Group reports a strong quarter")],
            ticker="AAPL",
            company_name="Apple Inc.",
        )
        assert result["analyzed_articles_count"] == 0

    def test_without_identifiers_nothing_is_filtered(self, agent):
        result = agent.run([article("Markets rally broadly")])
        assert result["analyzed_articles_count"] == 1


class TestRecencyWeighting:
    def test_recent_articles_dominate_older_ones(self, agent):
        """Fresh bad news should outweigh a stale positive story."""
        result = agent.run(
            [
                article("Acme Industries shares plunge after guidance cut", age_days=0.5),
                article("Acme Industries shares surge to record", age_days=25),
            ],
            ticker="TEST",
            company_name="Acme Industries",
        )
        assert result["average_sentiment_compound"] < 0
        assert result["analyzed_articles_count"] == 2

    def test_stale_articles_are_dropped(self, agent):
        result = agent.run(
            [article("Acme Industries beats estimates", age_days=200)],
            ticker="TEST",
            company_name="Acme Industries",
        )
        assert result["analyzed_articles_count"] == 0
        assert result["excluded_stale_count"] == 1

    def test_missing_and_malformed_dates_are_tolerated(self, agent):
        articles = [
            {"title": "Acme Industries beats estimates", "description": ""},
            {"title": "Acme Industries upgraded", "description": "", "publishedAt": "not-a-date"},
        ]
        result = agent.run(articles, ticker="TEST", company_name="Acme Industries")
        assert result["analyzed_articles_count"] == 2

    def test_future_timestamps_do_not_inflate_weight(self, agent):
        result = agent.run(
            [article("Acme Industries beats estimates", age_days=-2)],
            ticker="TEST",
            company_name="Acme Industries",
        )
        assert result["analyzed_articles_count"] == 1


class TestPayload:
    def test_empty_input_returns_a_neutral_reading(self, agent):
        result = agent.run([])
        assert result["average_sentiment_compound"] == 0.0
        assert result["analyzed_articles_count"] == 0
        assert "note" in result

    def test_headline_extremes_are_reported(self, agent):
        result = agent.run(
            [
                article("Acme Industries shares surge to a record high"),
                article("Acme Industries faces fraud investigation"),
                article("Acme Industries names a new board member"),
            ],
            ticker="TEST",
            company_name="Acme Industries",
        )
        assert result["most_positive_headline"] is not None
        assert "fraud" in result["most_negative_headline"].lower()

    def test_counts_are_consistent(self, agent):
        result = agent.run(
            [
                article("Acme Industries beats estimates"),
                article("Acme Industries misses estimates"),
                article("Acme Industries announces annual meeting date"),
            ],
            ticker="TEST",
            company_name="Acme Industries",
        )
        total = (
            result["positive_articles_count"]
            + result["negative_articles_count"]
            + result["neutral_articles_count"]
        )
        assert total == result["analyzed_articles_count"]
