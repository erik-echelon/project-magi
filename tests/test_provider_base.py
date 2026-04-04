"""Tests for the provider base types and protocol."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from project_magi.providers.base import Attachment, Message, ProviderResponse


class TestAttachment:
    def test_from_path_png(self, tmp_path: Path) -> None:
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes

        att = Attachment.from_path(img)

        assert att.media_type == "image/png"
        assert att.data == b"\x89PNG\r\n\x1a\n"
        assert att.filename == "test.png"

    def test_from_path_pdf(self, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        att = Attachment.from_path(pdf)

        assert att.media_type == "application/pdf"
        assert att.filename == "doc.pdf"

    def test_from_path_unknown_type(self, tmp_path: Path) -> None:
        f = tmp_path / "data.qqqxyz"
        f.write_bytes(b"hello")

        att = Attachment.from_path(f)

        assert att.media_type == "application/octet-stream"

    def test_base64_data(self) -> None:
        att = Attachment(media_type="text/plain", data=b"hello world")

        assert att.base64_data == "aGVsbG8gd29ybGQ="

    def test_from_path_string(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            f.flush()
            att = Attachment.from_path(f.name)  # str, not Path

        assert att.media_type == "text/plain"
        assert att.data == b"test content"
        Path(f.name).unlink()

    def test_frozen(self) -> None:
        att = Attachment(media_type="text/plain", data=b"x")
        with pytest.raises(AttributeError):
            setattr(att, "media_type", "other")  # noqa: B010


class TestMessage:
    def test_create_user_message(self) -> None:
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_create_assistant_message(self) -> None:
        msg = Message(role="assistant", content="hi there")
        assert msg.role == "assistant"
        assert msg.content == "hi there"

    def test_frozen(self) -> None:
        msg = Message(role="user", content="x")
        with pytest.raises(AttributeError):
            setattr(msg, "role", "assistant")  # noqa: B010


class TestProviderResponse:
    def test_create_minimal(self) -> None:
        resp = ProviderResponse(content="hello", model="claude-sonnet-4-20250514")
        assert resp.content == "hello"
        assert resp.model == "claude-sonnet-4-20250514"
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.stop_reason == ""
        assert resp.raw == {}

    def test_create_full(self) -> None:
        resp = ProviderResponse(
            content="answer",
            model="claude-sonnet-4-20250514",
            input_tokens=100,
            output_tokens=50,
            stop_reason="end_turn",
            raw={"id": "msg_123"},
        )
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.stop_reason == "end_turn"
        assert resp.raw["id"] == "msg_123"
