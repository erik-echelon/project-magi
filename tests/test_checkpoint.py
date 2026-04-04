"""Tests for checkpoint action parsing."""

from __future__ import annotations

from project_magi.coordinator.checkpoint import (
    ContinueAction,
    ContinueWithFeedbackAction,
    RedirectPersonaAction,
    WrapUpAction,
    parse_checkpoint_response,
)

KNOWN_PERSONAS = ["melchior", "balthasar", "casper"]


class TestWrapUp:
    def test_wrap_up(self) -> None:
        assert isinstance(parse_checkpoint_response("wrap up"), WrapUpAction)

    def test_stop(self) -> None:
        assert isinstance(parse_checkpoint_response("stop"), WrapUpAction)

    def test_done(self) -> None:
        assert isinstance(parse_checkpoint_response("done"), WrapUpAction)

    def test_finish(self) -> None:
        assert isinstance(parse_checkpoint_response("finish"), WrapUpAction)

    def test_thats_enough(self) -> None:
        assert isinstance(parse_checkpoint_response("that's enough"), WrapUpAction)

    def test_looks_good(self) -> None:
        assert isinstance(parse_checkpoint_response("looks good"), WrapUpAction)

    def test_this_is_good(self) -> None:
        assert isinstance(parse_checkpoint_response("this is good"), WrapUpAction)

    def test_case_insensitive(self) -> None:
        assert isinstance(parse_checkpoint_response("Wrap Up"), WrapUpAction)


class TestContinue:
    def test_keep_going(self) -> None:
        result = parse_checkpoint_response("keep going")
        assert isinstance(result, ContinueAction)

    def test_continue(self) -> None:
        result = parse_checkpoint_response("continue")
        assert isinstance(result, ContinueAction)

    def test_another_round(self) -> None:
        result = parse_checkpoint_response("another round")
        assert isinstance(result, ContinueAction)

    def test_keep_going_with_period(self) -> None:
        result = parse_checkpoint_response("keep going.")
        assert isinstance(result, ContinueAction)


class TestContinueWithFeedback:
    def test_keep_going_but(self) -> None:
        result = parse_checkpoint_response("keep going, but consider the budget")
        assert isinstance(result, ContinueWithFeedbackAction)
        assert result.feedback == "consider the budget"

    def test_keep_going_but_no_comma(self) -> None:
        result = parse_checkpoint_response("keep going but consider costs")
        assert isinstance(result, ContinueWithFeedbackAction)
        assert result.feedback == "consider costs"

    def test_continue_but(self) -> None:
        result = parse_checkpoint_response("continue, but add security analysis")
        assert isinstance(result, ContinueWithFeedbackAction)
        assert result.feedback == "add security analysis"

    def test_arbitrary_feedback(self) -> None:
        result = parse_checkpoint_response(
            "I don't see cost analysis reflected in any of the personas"
        )
        assert isinstance(result, ContinueWithFeedbackAction)
        assert "cost analysis" in result.feedback


class TestRedirectPersona:
    def test_redirect_known_persona(self) -> None:
        result = parse_checkpoint_response(
            "melchior isn't considering the team impact",
            known_persona_names=KNOWN_PERSONAS,
        )
        assert isinstance(result, RedirectPersonaAction)
        assert result.persona_name == "melchior"
        assert "team impact" in result.feedback

    def test_redirect_another_persona(self) -> None:
        result = parse_checkpoint_response(
            "casper should focus more on the technical feasibility",
            known_persona_names=KNOWN_PERSONAS,
        )
        assert isinstance(result, RedirectPersonaAction)
        assert result.persona_name == "casper"

    def test_unknown_persona_becomes_feedback(self) -> None:
        result = parse_checkpoint_response(
            "unknown_persona isn't right",
            known_persona_names=KNOWN_PERSONAS,
        )
        # Not a known persona, so treated as general feedback
        assert isinstance(result, ContinueWithFeedbackAction)

    def test_no_known_personas_falls_to_feedback(self) -> None:
        result = parse_checkpoint_response("melchior should reconsider")
        assert isinstance(result, ContinueWithFeedbackAction)


class TestEdgeCases:
    def test_empty_string(self) -> None:
        result = parse_checkpoint_response("")
        assert isinstance(result, ContinueAction)

    def test_whitespace_only(self) -> None:
        result = parse_checkpoint_response("   ")
        assert isinstance(result, ContinueAction)
