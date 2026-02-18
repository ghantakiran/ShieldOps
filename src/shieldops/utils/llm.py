"""Shared LLM client for ShieldOps agents.

Wraps langchain-anthropic with structured output support.
All agent nodes use this client for analysis and reasoning.
"""

from typing import Any

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from shieldops.config import settings

logger = structlog.get_logger()

# Module-level singleton (lazy-initialized)
_llm_instance: ChatAnthropic | None = None


def get_llm() -> ChatAnthropic:
    """Get or create the shared LLM client."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            max_tokens=4096,
            temperature=0.1,  # Low temp for deterministic infrastructure reasoning
        )
    return _llm_instance


async def llm_analyze(
    system_prompt: str,
    user_prompt: str,
    response_schema: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Run an LLM analysis with optional structured output.

    Args:
        system_prompt: System instructions for the analysis task.
        user_prompt: The data/context to analyze.
        response_schema: If provided, parse response as this Pydantic model.

    Returns:
        Parsed dict from LLM response.
    """
    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    if response_schema is not None:
        parser = JsonOutputParser(pydantic_object=response_schema)
        format_instructions = parser.get_format_instructions()
        messages[0] = SystemMessage(
            content=f"{system_prompt}\n\n{format_instructions}"
        )
        response = await llm.ainvoke(messages)
        return parser.parse(response.content)

    response = await llm.ainvoke(messages)
    return {"content": response.content}


async def llm_structured(
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
) -> BaseModel:
    """Run LLM analysis and return a validated Pydantic model.

    Uses Claude's native tool_use for reliable structured output.
    """
    llm = get_llm()
    structured_llm = llm.with_structured_output(schema)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    return await structured_llm.ainvoke(messages)
