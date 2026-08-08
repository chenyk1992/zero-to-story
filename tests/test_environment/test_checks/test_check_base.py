"""Tests for the unified Check Framework."""
from __future__ import annotations

import pytest

from lfo.environment.checks.base import (
    CheckContext,
    CheckResult,
    CheckRunner,
    CheckSeverity,
    CheckStatus,
    check,
)


class TestCheckSeverity:
    def test_values(self):
        assert CheckSeverity.INFO.value == "info"
        assert CheckSeverity.WARNING.value == "warning"
        assert CheckSeverity.BLOCKER.value == "blocker"


class TestCheckStatus:
    def test_values(self):
        assert CheckStatus.PASSED.value == "passed"
        assert CheckStatus.FAILED.value == "failed"
        assert CheckStatus.SKIPPED.value == "skipped"


class TestCheckResult:
    def test_frozen(self):
        r = CheckResult(
            check_id="test",
            severity=CheckSeverity.INFO,
            status=CheckStatus.PASSED,
            message="ok",
        )
        with pytest.raises(AttributeError):
            r.check_id = "other"

    def test_with_details(self):
        r = CheckResult(
            check_id="test",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.FAILED,
            message="fail",
            details={"key": "value"},
            remediation="fix it",
        )
        assert r.details == {"key": "value"}
        assert r.remediation == "fix it"


class TestCheckContext:
    def test_defaults(self):
        ctx = CheckContext()
        assert ctx.machine_profile is None
        assert ctx.required_workflow_ids == set()
        assert ctx.required_model_ids == set()
        assert ctx.required_tools == set()
        assert ctx.required_storage_bytes == 0


class TestCheckDecorator:
    def test_attaches_metadata(self):
        @check("my.check", severity=CheckSeverity.BLOCKER, description="A check")
        def my_check(ctx: CheckContext) -> CheckResult:
            return CheckResult(
                check_id="my.check",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.PASSED,
                message="ok",
            )

        assert my_check._check_id == "my.check"
        assert my_check._severity == CheckSeverity.BLOCKER
        assert my_check._description == "A check"


class TestCheckRunner:
    def test_register_and_run(self):
        runner = CheckRunner()

        @check("test.pass")
        def passing_check(ctx: CheckContext) -> CheckResult:
            return CheckResult(
                check_id="test.pass",
                severity=CheckSeverity.INFO,
                status=CheckStatus.PASSED,
                message="passed",
            )

        runner.register(passing_check)
        results = runner.run(CheckContext())
        assert len(results) == 1
        assert results[0].status == CheckStatus.PASSED

    def test_run_multiple(self):
        runner = CheckRunner()

        @check("check.one")
        def one(ctx: CheckContext) -> CheckResult:
            return CheckResult("check.one", CheckSeverity.INFO, CheckStatus.PASSED, "ok")

        @check("check.two")
        def two(ctx: CheckContext) -> CheckResult:
            return CheckResult("check.two", CheckSeverity.WARNING, CheckStatus.FAILED, "bad")

        runner.register(one)
        runner.register(two)
        results = runner.run(CheckContext())
        assert len(results) == 2

    def test_exception_converted_to_failed(self):
        runner = CheckRunner()

        @check("check.broken")
        def broken(ctx: CheckContext) -> CheckResult:
            raise RuntimeError("boom")

        runner.register(broken)
        results = runner.run(CheckContext())
        assert len(results) == 1
        assert results[0].status == CheckStatus.FAILED
        assert "boom" in results[0].message

    def test_run_subset(self):
        runner = CheckRunner()

        @check("check.a")
        def a(ctx: CheckContext) -> CheckResult:
            return CheckResult("check.a", CheckSeverity.INFO, CheckStatus.PASSED, "ok")

        @check("check.b")
        def b(ctx: CheckContext) -> CheckResult:
            return CheckResult("check.b", CheckSeverity.INFO, CheckStatus.PASSED, "ok")

        runner.register(a)
        runner.register(b)
        results = runner.run_subset(CheckContext(), {"check.a"})
        assert len(results) == 1
        assert results[0].check_id == "check.a"

    def test_registered_check_ids(self):
        runner = CheckRunner()

        @check("id.one")
        def one(ctx: CheckContext) -> CheckResult:
            return CheckResult("id.one", CheckSeverity.INFO, CheckStatus.PASSED, "ok")

        @check("id.two")
        def two(ctx: CheckContext) -> CheckResult:
            return CheckResult("id.two", CheckSeverity.INFO, CheckStatus.PASSED, "ok")

        runner.register(one)
        runner.register(two)
        ids = runner.registered_check_ids
        assert "id.one" in ids
        assert "id.two" in ids
