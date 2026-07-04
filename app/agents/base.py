import asyncio
import logging
from typing import Optional, Tuple
from openai import AsyncOpenAI
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Placeholder / mock values that indicate a key is not actually configured.
PLACEHOLDER_KEYS = {
    "", "mock_key",
    "your_openrouter_api_key", "your_openrouter_api_key_here",
    "your_groq_api_key", "your_groq_api_key_here",
}

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Detect whether the Hermes Agent framework (Nous Research) is importable in this env.
try:
    from run_agent import AIAgent as _HermesAIAgent  # type: ignore
    HERMES_AVAILABLE = True
except Exception:  # pragma: no cover - depends on optional install
    _HermesAIAgent = None
    HERMES_AVAILABLE = False


def resolve_llm_config() -> Tuple[Optional[str], str, str, str]:
    """
    Resolve the effective LLM provider configuration.

    Provider preference: Groq (fast, free models) first, then OpenRouter.
    Returns (api_key, base_url, model, provider_label). api_key is None when no
    real credentials are configured, signalling the deterministic fallback path.
    """
    if settings.groq_api_key not in PLACEHOLDER_KEYS:
        base_url = settings.llm_base_url or GROQ_BASE_URL
        return settings.groq_api_key, base_url, settings.llm_model, "groq"
    if settings.openrouter_api_key not in PLACEHOLDER_KEYS:
        base_url = settings.llm_base_url or OPENROUTER_BASE_URL
        return settings.openrouter_api_key, base_url, settings.llm_model, "openrouter"
    return None, OPENROUTER_BASE_URL, settings.llm_model, "none"


def llm_configured() -> bool:
    """Return True only when a real (non-placeholder) LLM key is present."""
    api_key, _, _, _ = resolve_llm_config()
    return api_key is not None


# Backwards-compatible alias (older callers imported this name).
def openrouter_configured() -> bool:
    return llm_configured()


def hermes_active() -> bool:
    """True when the Hermes framework is installed, enabled, and has a live key."""
    return HERMES_AVAILABLE and settings.use_hermes and llm_configured()


class BaseAgent:
    """
    Base class for the specialist agents.

    Reasoning backend, in order of preference:
      1. Nous Research **Hermes Agent** framework (`run_agent.AIAgent`) when installed
         and enabled via USE_HERMES — this is the framework required by the assignment.
      2. A direct OpenAI-compatible client (Groq or OpenRouter) as a lightweight path.
      3. A deterministic offline fallback when no credentials are configured.
    """

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt

        api_key, base_url, model, provider = resolve_llm_config()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.provider = provider

        if api_key is None:
            logger.warning(
                f"Agent [{self.name}]: no LLM key configured; using deterministic fallback."
            )
            self.client = None
        else:
            self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

        if hermes_active():
            logger.info(f"Agent [{self.name}] using Hermes Agent framework via {self.provider}.")

    async def chat(self, prompt: str, system_prompt_override: Optional[str] = None) -> str:
        """Query the reasoning backend with the agent persona and user prompt."""
        sys_prompt = system_prompt_override or self.system_prompt

        if not llm_configured():
            return self._generate_fallback_response(prompt)

        # 1. Preferred path: the Hermes Agent framework.
        if hermes_active():
            try:
                return await self._chat_hermes(prompt, sys_prompt)
            except Exception as e:
                logger.error(f"Agent [{self.name}] Hermes query failed: {e}", exc_info=True)
                # Fall through to the direct client path.

        # 2. Direct OpenAI-compatible client (Groq / OpenRouter).
        try:
            logger.info(f"Agent [{self.name}] querying {self.provider} ({self.model})")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for analytical quantitative reasoning
                max_tokens=1500,
            )
            output = response.choices[0].message.content
            logger.info(f"Agent [{self.name}] received response successfully.")
            return output
        except Exception as e:
            logger.error(f"Agent [{self.name}] {self.provider} query failed: {e}", exc_info=True)
            return self._generate_fallback_response(prompt, error=e)

    async def _chat_hermes(self, prompt: str, sys_prompt: str) -> str:
        """
        Run a single-turn Hermes Agent completion.

        Hermes' AIAgent.chat() is synchronous and must not be shared across concurrent
        calls, so a fresh instance is created per call and executed in a worker thread.
        Autonomous tool loops are disabled — the specialist agents supply their own data,
        and the quantitative model remains authoritative for trade decisions.
        """
        def _run() -> str:
            agent = _HermesAIAgent(
                base_url=self.base_url,
                api_key=self.api_key,
                provider="openai",
                model=self.model,
                quiet_mode=True,
                skip_memory=True,
                skip_context_files=True,
                load_soul_identity=False,
                disabled_toolsets=["all"],
                max_iterations=1,
                ephemeral_system_prompt=sys_prompt,
            )
            return agent.chat(prompt)

        logger.info(f"Agent [{self.name}] querying Hermes Agent ({self.model} via {self.provider})")
        output = await asyncio.to_thread(_run)
        logger.info(f"Agent [{self.name}] received Hermes response successfully.")
        return output

    def _generate_fallback_response(self, prompt: str, error: Optional[Exception] = None) -> str:
        """Deterministic offline response when no LLM credentials are configured."""
        logger.warning(f"Agent [{self.name}] generating fallback mock response due to API unavailability.")

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
