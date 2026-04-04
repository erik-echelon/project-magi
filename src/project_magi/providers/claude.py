"""Claude provider implementation using the Anthropic Python SDK."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

import anthropic

from project_magi.providers.base import Attachment, Message, ProviderResponse

if TYPE_CHECKING:
    from anthropic.types import MessageParam

# Default model for V1
DEFAULT_MODEL = "claude-opus-4-20250514"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 300.0


class ClaudeProvider:
    """LLM provider backed by the Anthropic Claude API.

    Reads the API key from the ANTHROPIC_API_KEY environment variable.
    Supports text, image, and PDF attachments.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: str | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            msg = (
                "No API key provided. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key to ClaudeProvider."
            )
            raise ValueError(msg)

        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(
            api_key=resolved_key,
            timeout=timeout,
        )

    async def send_message(
        self,
        system_prompt: str,
        messages: list[Message],
        attachments: list[Attachment] | None = None,
    ) -> ProviderResponse:
        """Send a message to Claude and return the response."""
        api_messages = self._build_messages(messages, attachments)

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=api_messages,
        )

        content = self._extract_text(response)

        return ProviderResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason or "",
            raw=response.model_dump(),
        )

    def _build_messages(
        self,
        messages: list[Message],
        attachments: list[Attachment] | None,
    ) -> list[MessageParam]:
        """Convert Message objects to the Anthropic API format."""
        api_messages: list[MessageParam] = []

        for i, msg in enumerate(messages):
            # Attach files to the first user message
            if i == 0 and msg.role == "user" and attachments:
                content_blocks: list[dict[str, Any]] = []
                for att in attachments:
                    content_blocks.append(self._attachment_to_block(att))
                content_blocks.append({"type": "text", "text": msg.content})
                msg_param = cast(
                    "MessageParam",
                    {
                        "role": msg.role,
                        "content": content_blocks,
                    },
                )
                api_messages.append(msg_param)
            else:
                api_messages.append(
                    cast("MessageParam", {"role": msg.role, "content": msg.content})
                )

        return api_messages

    def _attachment_to_block(self, att: Attachment) -> dict[str, Any]:
        """Convert an Attachment to an Anthropic content block."""
        if att.media_type == "application/pdf":
            return {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": att.media_type,
                    "data": att.base64_data,
                },
            }
        if att.media_type.startswith("image/"):
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": att.media_type,
                    "data": att.base64_data,
                },
            }
        # Fallback: treat as text
        return {
            "type": "text",
            "text": f"[Attachment: {att.filename}]\n{att.data.decode('utf-8', errors='replace')}",
        }

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        """Extract text content from an Anthropic response."""
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
