import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.research.client import ResearchClient

logger = logging.getLogger(__name__)

class ResearchAgent(BaseAgent):
    """
    Agent 4: Research Agent.
    Searches web news, Twitter/social mentions, climate reports, and news blogs for weather hazards and sentiments.
    """
    
    SYSTEM_PROMPT = (
        "You are the Research Agent. Your job is to read and analyze unstructured text from search results, "
        "news wires, and social updates. Look for anomalies, consensus among meteorologists, climate reports, "
        "and local chatter regarding upcoming weather events. Assign a sentiment score and compile sources."
    )

    def __init__(self, research_client: Optional[ResearchClient] = None):
        super().__init__(name="ResearchAgent", system_prompt=self.SYSTEM_PROMPT)
        self.research = research_client or ResearchClient()

    async def perform_research(self, city_name: str) -> Dict[str, Any]:
        """Perform news and general search on weather developments for a city"""
        query_news = f"{city_name} weather alert storm rain flood heatwave"
        
        logger.info(f"ResearchAgent searching news for '{query_news}'")
        news_results = self.research.search_news(query_news, max_results=4)
        
        # Fallback to general search if news is empty
        if not news_results:
            logger.info("News results empty. Performing general web search.")
            news_results = self.research.search_general(f"{city_name} weather forecast warning", max_results=3)
            
        # Format the text snippets for LLM analysis
        search_text = ""
        sources = []
        for i, r in enumerate(news_results):
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("url", "")
            sources.append(url)
            search_text += f"Source {i+1} [{title}]: {body}\n\n"
            
        if not search_text:
            search_text = "No recent news articles or warnings found on web search."
            
        prompt = (
            f"Review these recent news snippets and search results regarding {city_name} weather conditions:\n\n"
            f"{search_text}"
            "Extract any mentions of severe weather alerts, precipitation risks, cyclones, floods, or heatwaves. "
            "Formulate an AI summary of the situation. Rate the overall sentiment regarding rain/heat (e.g. positive/negative for rain) "
            "and output a JSON string containing:\n"
            "{\n"
            '  "summary": "AI summary of weather news",\n'
            '  "sentiment_score": float,  // range [-1.0 (very dry/hot/clear) to 1.0 (stormy/heavy rain/flood alert)]\n'
            '  "confidence": float  // range [0.0 to 1.0]\n'
            "}"
        )
        
        response = await self.chat(prompt)
        
        # Parse output JSON or load default if LLM returns text
        import json
        try:
            # Look for JSON block in the LLM response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end != -1:
                json_data = json.loads(response[start:end])
                return {
                    "success": True,
                    "summary": json_data.get("summary", response),
                    "sentiment_score": float(json_data.get("sentiment_score", 0.0)),
                    "confidence": float(json_data.get("confidence", 0.5)),
                    "sources": sources
                }
        except Exception as e:
            logger.warning(f"ResearchAgent failed to parse LLM response as JSON. Output: {response}. Error: {e}")
            
        return {
            "success": True,
            "summary": response,
            "sentiment_score": 0.0,
            "confidence": 0.5,
            "sources": sources
        }
