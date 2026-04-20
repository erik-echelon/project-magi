"""Provider protocol and shared types."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Attachment:
    """A file attachment to include in a message.

    Can be constructed from a file path or from raw bytes.
    """

    media_type: str
    data: bytes
    filename: str = ""

    @classmethod
    def from_path(cls, path: str | Path) -> Attachment:
        """Create an attachment from a file path."""
        p = Path(path)
        mime_type = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return cls(
            media_type=mime_type,
            data=p.read_bytes(),
            filename=p.name,
        )

    @property
    def base64_data(self) -> str:
        """Return the attachment data as a base64-encoded string."""
        return base64.standard_b64encode(self.data).decode("ascii")


@dataclass(frozen=True)
class Message:
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class ProviderResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""
    raw: dict = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """Protocol for LLM providers.

    Implementations must provide a send_message method that takes a system
    prompt, a list of messages, and optional attachments, and returns a
    ProviderResponse. This is the only interface the MAGI engine uses to
    communicate with LLMs — implementing this protocol is all that's needed
    to add a new backend.
    """

    async def send_message(
        self,
        system_prompt: str,
        messages: list[Message],
        attachments: list[Attachment] | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        """Send a message to the LLM and return the response."""
        ...
