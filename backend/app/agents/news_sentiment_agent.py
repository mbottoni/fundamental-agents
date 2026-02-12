import logging
from typing import Any, Optional

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

logger = logging.getLogger("stock_analyzer.agents.news_sentiment")


class NewsSentimentAgent:
    """Analyzes sentiment from news articles using VADER."""

    POSITIVE_THRESHOLD = 0.05
    NEGATIVE_THRESHOLD = -0.05

    def __init__(self) -> None:
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            logger.info("Downloading VADER lexicon...")
            nltk.download("vader_lexicon", quiet=True)
        self.sia = SentimentIntensityAnalyzer()

    def analyze_sentiment(self, text: str) -> Optional[dict[str, float]]:
        """Analyze the sentiment of a given text string."""
        if not text or not text.strip():
            return None
        return self.sia.polarity_scores(text)

    def run(self, news_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze sentiment across a list of news articles."""
        logger.info("Analyzing sentiment for %d articles", len(news_data))

        sentiments: list[dict[str, float]] = []

        for article in news_data:
            title = article.get("title", "") or ""
            description = article.get("description", "") or ""
            content_to_analyze = f"{title}. {description}".strip()

            if content_to_analyze and content_to_analyze != ".":
                sentiment = self.analyze_sentiment(content_to_analyze)
                if sentiment:
                    sentiments.append(sentiment)

        if not sentiments:
            logger.warning("No articles available for sentiment analysis")
            return {
                "average_sentiment_compound": 0.0,
                "positive_articles_count": 0,
                "negative_articles_count": 0,
                "neutral_articles_count": 0,
                "analyzed_articles_count": 0,
            }

        avg_compound = sum(s["compound"] for s in sentiments) / len(sentiments)

        positive = sum(1 for s in sentiments if s["compound"] > self.POSITIVE_THRESHOLD)
        negative = sum(1 for s in sentiments if s["compound"] < self.NEGATIVE_THRESHOLD)
        neutral = len(sentiments) - positive - negative

        result = {
            "average_sentiment_compound": round(avg_compound, 4),
            "positive_articles_count": positive,
            "negative_articles_count": negative,
            "neutral_articles_count": neutral,
            "analyzed_articles_count": len(sentiments),
        }

        logger.info(
            "Sentiment analysis complete: avg=%.4f, pos=%d, neg=%d, neutral=%d",
            avg_compound, positive, negative, neutral,
        )

        return result
