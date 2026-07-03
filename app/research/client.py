import logging
from typing import List, Dict, Any, Optional
from ddgs import DDGS

logger = logging.getLogger(__name__)

class ResearchClient:
    """Client for performing web search research on weather events and market context"""
    
    def __init__(self):
        pass

    def search_news(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search DuckDuckGo News for the given query"""
        try:
            logger.info(f"Searching DuckDuckGo News for query: '{query}'")
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=max_results))
                return [
                    {
                        "title": r.get("title"),
                        "body": r.get("body"),
                        "url": r.get("url"),
                        "source": r.get("source"),
                        "date": r.get("date")
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo News: {e}", exc_info=True)
            return []

    def search_general(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search DuckDuckGo Text for the given query"""
        try:
            logger.info(f"Searching DuckDuckGo Text for query: '{query}'")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return [
                    {
                        "title": r.get("title"),
                        "body": r.get("body"),
                        "url": r.get("href")
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo Text: {e}", exc_info=True)
            return []
