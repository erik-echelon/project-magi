"""Tests for the Claude provider implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Generator

import anthropic
import pytest

from project_magi.providers.base import Attachment, Message
from project_magi.providers.claude import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, ClaudeProvider


def _make_mock_response(
    text: str = "Hello!",
    model: str = DEFAULT_MODEL,
    input_tokens: int = 10,
    output_tokens: int = 5,
    stop_reason: str = "end_turn",
) -> MagicMock:
    """Create a mock Anthropic Message response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.content = [text_block]
    response.model = model
    response.usage = usage
    response.stop_reason = stop_reason
    response.model_dump.return_value = {
        "id": "msg_test",
        "content": [{"type": "text", "text": text}],
        "model": model,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "stop_reason": stop_reason,
    }
    return response


class TestClaudeProviderInit:
    def test_requires_api_key(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(ValueError, match="No API key provided"),
        ):
            ClaudeProvider()

    def test_accepts_explicit_key(self) -> None:
        provider = ClaudeProvider(api_key="sk-ant-test-key")
        assert provider.model == DEFAULT_MODEL

    def test_reads_env_key(self) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-env-key"}):
            provider = ClaudeProvider()
            assert provider.model == DEFAULT_MODEL

    def test_custom_model(self) -> None:
        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-haiku-4-5-20251001")
        assert provider.model == "claude-haiku-4-5-20251001"

    def test_custom_max_tokens(self) -> None:
        provider = ClaudeProvider(api_key="sk-ant-test", max_tokens=8192)
        assert provider.max_tokens == 8192


class TestClaudeProviderSendMessage:
    @pytest.fixture
    def provider(self) -> ClaudeProvider:
        return ClaudeProvider(api_key="sk-ant-test-key")

    @pytest.fixture
    def mock_create(self, provider: ClaudeProvider) -> Generator[AsyncMock, None, None]:
        """Patch the messages.create method on the provider's client."""
        mock = AsyncMock()
        with patch.object(provider._client.messages, "create", mock):
            yield mock

    @pytest.mark.asyncio
    async def test_basic_message(self, provider: ClaudeProvider, mock_create: AsyncMock) -> None:
        mock_create.return_value = _make_mock_response(text="Test response")

        result = await provider.send_message(
            system_prompt="You are helpful.",
            messages=[Message(role="user", content="Hello")],
        )

        assert result.content == "Test response"
        assert result.model == DEFAULT_MODEL
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.stop_reason == "end_turn"
        assert result.raw["id"] == "msg_test"

    @pytest.mark.asyncio
    async def test_calls_api_with_correct_params(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.return_value = _make_mock_response()

        await provider.send_message(
            system_prompt="Be concise.",
            messages=[Message(role="user", content="Hi")],
        )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == DEFAULT_MODEL
        assert call_kwargs["max_tokens"] == DEFAULT_MAX_TOKENS
        assert call_kwargs["system"] == "Be concise."

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.return_value = _make_mock_response(text="Sure!")

        messages = [
            Message(role="user", content="What is 2+2?"),
            Message(role="assistant", content="4"),
            Message(role="user", content="Are you sure?"),
        ]

        result = await provider.send_message(
            system_prompt="You are a math tutor.",
            messages=messages,
        )

        assert result.content == "Sure!"
        call_kwargs = mock_create.call_args.kwargs
        assert len(call_kwargs["messages"]) == 3

    @pytest.mark.asyncio
    async def test_with_image_attachment(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.return_value = _make_mock_response(text="I see an image")

        att = Attachment(media_type="image/png", data=b"\x89PNG", filename="test.png")

        await provider.send_message(
            system_prompt="Describe images.",
            messages=[Message(role="user", content="What is this?")],
            attachments=[att],
        )

        call_kwargs = mock_create.call_args.kwargs
        first_msg = call_kwargs["messages"][0]
        assert first_msg["role"] == "user"
        assert isinstance(first_msg["content"], list)
        assert first_msg["content"][0]["type"] == "image"
        assert first_msg["content"][0]["source"]["media_type"] == "image/png"
        assert first_msg["content"][-1]["type"] == "text"
        assert first_msg["content"][-1]["text"] == "What is this?"

    @pytest.mark.asyncio
    async def test_with_pdf_attachment(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.return_value = _make_mock_response(text="PDF contents")

        att = Attachment(media_type="application/pdf", data=b"%PDF-1.4", filename="doc.pdf")

        await provider.send_message(
            system_prompt="Read documents.",
            messages=[Message(role="user", content="Summarize this.")],
            attachments=[att],
        )

        call_kwargs = mock_create.call_args.kwargs
        first_msg = call_kwargs["messages"][0]
        assert first_msg["content"][0]["type"] == "document"
        assert first_msg["content"][0]["source"]["media_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_with_text_attachment_fallback(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.return_value = _make_mock_response(text="Got it")

        att = Attachment(media_type="text/plain", data=b"Some code here", filename="main.py")

        await provider.send_message(
            system_prompt="Review code.",
            messages=[Message(role="user", content="Review this.")],
            attachments=[att],
        )

        call_kwargs = mock_create.call_args.kwargs
        first_msg = call_kwargs["messages"][0]
        assert first_msg["content"][0]["type"] == "text"
        assert "[Attachment: main.py]" in first_msg["content"][0]["text"]
        assert "Some code here" in first_msg["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_attachments_only_on_first_user_message(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.return_value = _make_mock_response()

        att = Attachment(media_type="image/png", data=b"\x89PNG", filename="img.png")

        await provider.send_message(
            system_prompt="test",
            messages=[
                Message(role="user", content="First"),
                Message(role="assistant", content="OK"),
                Message(role="user", content="Second"),
            ],
            attachments=[att],
        )

        call_kwargs = mock_create.call_args.kwargs
        msgs = call_kwargs["messages"]
        # First message has attachment blocks
        assert isinstance(msgs[0]["content"], list)
        # Second user message is plain text
        assert msgs[2]["content"] == "Second"

    @pytest.mark.asyncio
    async def test_multiple_text_blocks_in_response(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        block1 = MagicMock()
        block1.type = "text"
        block1.text = "Part one."

        block2 = MagicMock()
        block2.type = "text"
        block2.text = "Part two."

        usage = MagicMock()
        usage.input_tokens = 10
        usage.output_tokens = 20

        response = MagicMock()
        response.content = [block1, block2]
        response.model = DEFAULT_MODEL
        response.usage = usage
        response.stop_reason = "end_turn"
        response.model_dump.return_value = {}

        mock_create.return_value = response

        result = await provider.send_message(
            system_prompt="test",
            messages=[Message(role="user", content="go")],
        )

        assert result.content == "Part one.\nPart two."

    @pytest.mark.asyncio
    async def test_api_timeout_raises(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_create.side_effect = anthropic.APITimeoutError(request=MagicMock())

        with pytest.raises(anthropic.APITimeoutError):
            await provider.send_message(
                system_prompt="test",
                messages=[Message(role="user", content="hello")],
            )

    @pytest.mark.asyncio
    async def test_rate_limit_raises(
        self, provider: ClaudeProvider, mock_create: AsyncMock
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        mock_resp.text = "rate limited"
        mock_resp.json.return_value = {"error": {"message": "rate limited"}}

        mock_create.side_effect = anthropic.RateLimitError(
            message="rate limited",
            response=mock_resp,
            body={"error": {"message": "rate limited"}},
        )

        with pytest.raises(anthropic.RateLimitError):
            await provider.send_message(
                system_prompt="test",
                messages=[Message(role="user", content="hello")],
            )


class TestProviderProtocol:
    def test_claude_provider_is_a_provider(self) -> None:
        from project_magi.providers.base import Provider

        assert issubclass(ClaudeProvider, Provider)
