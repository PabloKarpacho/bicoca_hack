from __future__ import annotations

import asyncio
import json
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, SecretStr

T = TypeVar("T", bound=BaseModel)


class Agent:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout: int = 40,
        tools: list[Any] | None = None,
    ) -> None:
        client = ChatOpenAI(
            api_key=SecretStr(api_key) if api_key else None,
            base_url=base_url[:-1] if base_url.endswith("/") else base_url,
            timeout=timeout,
        )
        self.tool_map = {tool.name: tool for tool in (tools or [])}
        self.llm_client = client.bind_tools(tools or [])

    async def ask(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 1,
    ) -> list[dict[str, Any]]:
        conversation = list(messages)
        while True:
            response = await self.llm_client.ainvoke(
                input=[{"role": "system", "content": system_prompt}] + conversation,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": response.additional_kwargs.get("tool_calls"),
                }
            )
            logger.debug("LLM agent raw response: {response}", response=response)

            tool_calls = response.additional_kwargs.get("tool_calls")
            if not tool_calls:
                break

            for tool_call in tool_calls:
                tool_call_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                tool_fn = self.tool_map.get(tool_name)
                if tool_fn is None:
                    logger.error(
                        "LLM agent tool not found: {tool_name}", tool_name=tool_name
                    )
                    return conversation

                logger.debug(
                    "LLM agent executing tool {tool_name} with args {tool_args}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
                tool_result = await tool_fn.ainvoke(tool_args)
                conversation.append(
                    {
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": tool_call_id,
                    }
                )

            await asyncio.sleep(0.1)

        return conversation

    async def structured_response(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str,
        pydantic_class: type[T],
        max_tokens: int = 1000,
        temperature: float = 1,
    ) -> T:
        structured_llm = self.llm_client.with_structured_output(
            pydantic_class,
            method="function_calling",
        )
        response = await structured_llm.ainvoke(
            input=[{"role": "system", "content": system_prompt}] + messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        logger.debug("LLM agent structured response: {response}", response=response)

        return response
