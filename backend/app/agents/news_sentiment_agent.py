import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

class NewsSentimentAgent:
    def __init__(self):
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except nltk.downloader.DownloadError:
            nltk.download('vader_lexicon')
        self.sia = SentimentIntensityAnalyzer()

    def analyze_sentiment(self, text: str):
        """
        Analyzes the sentiment of a given text.
        """
        if not text:
            return None
        return self.sia.polarity_scores(text)

    def run(self, news_data: list):
        """
        Analyzes the sentiment of a list of news articles.
        """
        sentiments = []
        for article in news_data:
            title = article.get('title', '')
            description = article.get('description', '')
            
            # Combine title and description for a more comprehensive analysis
            content_to_analyze = f"{title}. {description}"
            
            if content_to_analyze.strip():
                sentiment = self.analyze_sentiment(content_to_analyze)
                if sentiment:
                    sentiments.append(sentiment)

        if not sentiments:
            return {
                "average_sentiment_compound": 0,
                "positive_articles_count": 0,
                "negative_articles_count": 0,
                "neutral_articles_count": 0,
                "analyzed_articles_count": 0
            }

        avg_compound = sum(s['compound'] for s in sentiments) / len(sentiments)
        
        positive_articles = sum(1 for s in sentiments if s['compound'] > 0.05)
        negative_articles = sum(1 for s in sentiments if s['compound'] < -0.05)
        neutral_articles = len(sentiments) - positive_articles - negative_articles

        return {
            "average_sentiment_compound": avg_compound,
            "positive_articles_count": positive_articles,
            "negative_articles_count": negative_articles,
            "neutral_articles_count": neutral_articles,
            "analyzed_articles_count": len(sentiments)
        } 