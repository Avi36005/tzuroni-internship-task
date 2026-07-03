import logging
from typing import Optional
from openai import AsyncOpenAI
from app.config.settings import settings

logger = logging.getLogger(__name__)

class BaseAgent:
    """
    Base Agent class wrapping OpenRouter API calls using OpenAI SDK.
    Serves as the foundation for the specialist agents.
    """
    
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        
        # Configure Async OpenAI client for OpenRouter
        api_key = settings.openrouter_api_key
        if not api_key or api_key == "mock_key":
            logger.warning("No OpenRouter API key found. Using mock credentials (llm calls will fail/mock).")
            
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = settings.llm_model

    async def chat(self, prompt: str, system_prompt_override: Optional[str] = None) -> str:
        """Query the LLM via OpenRouter with agent persona and user prompt"""
        sys_prompt = system_prompt_override or self.system_prompt
        
        try:
            logger.info(f"Agent [{self.name}] sending prompt to OpenRouter ({self.model})")
            
            # If the API key is not set, don't attempt request to avoid delays/exceptions
            if not settings.openrouter_api_key or settings.openrouter_api_key == "mock_key":
                return self._generate_fallback_response(prompt)
                
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for highly analytical quantitative reasoning
                max_tokens=1500
            )
            
            output = response.choices[0].message.content
            logger.info(f"Agent [{self.name}] received response successfully.")
            return output
            
        except Exception as e:
            logger.error(f"Agent [{self.name}] OpenRouter query failed: {e}", exc_info=True)
            return self._generate_fallback_response(prompt, error=e)

    def _generate_fallback_response(self, prompt: str, error: Optional[Exception] = None) -> str:
        """Fallback response generator if API keys are missing or OpenRouter fails"""
        logger.warning(f"Agent [{self.name}] generating fallback mock response due to API unavailability.")
        
        # Provide standard fallback reasoning depending on agent type
        if "prediction" in self.name.lower():
            return (
                "{\n"
                '  "probability": 0.55,\n'
                '  "confidence": 0.70,\n'
                '  "reasoning": "Fallback reasoning: APIs unavailable. Combined default priors indicate moderate chance of rain.",\n'
                '  "decision": "BUY YES"\n'
                "}"
            )
        elif "risk" in self.name.lower():
            return (
                "{\n"
                '  "status": "APPROVED",\n'
                '  "allocated_fraction": 0.02,\n'
                '  "allocated_dollars": 200.0,\n'
                '  "reason": "Fallback risk allocation: Kelly sized at 2% for capital protection."\n'
                "}"
            )
        else:
            return f"Agent {self.name} processed prompt: '{prompt[:50]}...'. Status: Active, API: Fallback."
