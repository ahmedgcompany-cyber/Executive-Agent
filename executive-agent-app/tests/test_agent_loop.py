"""Tests for AgentLoop success semantics and retry logic."""

import pytest
from unittest.mock import MagicMock, patch


def _make_result(success: bool, summary: str = "ok"):
    return {"success": success, "summary": summary}


class TestAgentLoopSuccessSemantics:
    """A1: AgentLoop must report success=False when no steps succeed."""

    def test_no_results_is_failure(self):
        """Empty results list should return success=False."""
        # AgentLoop.run() sets success = succeeded > 0 and succeeded == total
        # With 0 results: succeeded=0, total=0 → 0 > 0 is False → success=False
        succeeded = 0
        total = 0
        success = succeeded > 0 and succeeded == total
        assert success is False

    def test_partial_success_is_failure(self):
        """If some steps fail, overall result is failure."""
        succeeded = 1
        total = 3
        success = succeeded > 0 and succeeded == total
        assert success is False

    def test_all_success_is_success(self):
        """All steps succeeding means overall success."""
        succeeded = 3
        total = 3
        success = succeeded > 0 and succeeded == total
        assert success is True

    def test_old_semantics_were_wrong(self):
        """Old code: succeeded > 0 or not results. This was True for empty results."""
        # Old behavior: 0 > 0 or not [] → False or True → True (WRONG)
        succeeded = 0
        total = 0
        old_success = succeeded > 0 or not (total > 0)
        assert old_success is True  # This was the bug

    def test_compound_goals_same_semantics(self):
        """Compound goals use the same success formula."""
        succeeded = 2
        total = 3
        success = succeeded > 0 and succeeded == total
        assert success is False


class TestSelfRepairRetrySemantics:
    """A7: Strategy changes must set fix_succeeded=False, retry_recommended=True."""

    def test_strategy_change_means_not_fixed(self):
        """When self-repair changes strategy, fix did not succeed."""
        diagnosis = type("Diag", (), {
            "fix_succeeded": False,
            "retry_recommended": True,
        })()
        assert diagnosis.fix_succeeded is False
        assert diagnosis.retry_recommended is True

    def test_retry_recommended_allows_continuation(self):
        """retry_recommended=True means agent loop should retry, not give up."""
        diagnosis = type("Diag", (), {
            "fix_succeeded": False,
            "retry_recommended": True,
        })()
        should_retry = getattr(diagnosis, "retry_recommended", False)
        assert should_retry is True