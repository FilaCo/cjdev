"""The concurrency guarantees, which are the ones easiest to lose."""

import threading
import time

import pytest

from cjdev.application.runner import Outcome, Runner, Work
from cjdev.errors import UsageError


def work(label: str, action=lambda: None, key: str | None = None) -> Work[None]:
    return Work(key=key or label, label=label, action=action)


def labels(report) -> list[str]:
    return [r.label for r in report.results]


def outcomes(report) -> list[Outcome]:
    return [r.outcome for r in report.results]


class TestOrdering:
    def test_results_follow_submission_order_not_completion_order(self):
        # The transcript may not depend on scheduling. The first unit sleeps
        # so that it reliably finishes last.
        report = Runner(jobs=4).run(
            [
                work("slow", lambda: time.sleep(0.05)),
                work("fast-1"),
                work("fast-2"),
            ]
        )

        assert labels(report) == ["slow", "fast-1", "fast-2"]

    def test_jobs_of_one_runs_strictly_in_order(self):
        seen: list[str] = []
        report = Runner(jobs=1).run(
            [work(name, lambda name=name: seen.append(name)) for name in "abc"]
        )

        assert seen == ["a", "b", "c"]
        assert report.ok

    def test_an_empty_fan_out_is_not_an_error(self):
        assert Runner(jobs=4).run([]).ok


class TestKeysSerialise:
    def test_work_sharing_a_key_never_overlaps(self):
        # Two operations on one object store must not run at once, because
        # git does not serialise them for us.
        overlapping = False
        active = 0
        guard = threading.Lock()

        def touch() -> None:
            nonlocal overlapping, active
            with guard:
                active += 1
                overlapping = overlapping or active > 1
            time.sleep(0.02)
            with guard:
                active -= 1

        report = Runner(jobs=4).run(
            [work(f"unit-{i}", touch, key="same-store") for i in range(4)]
        )

        assert report.ok
        assert not overlapping

    def test_different_keys_do_overlap(self):
        started = threading.Barrier(3, timeout=2)

        report = Runner(jobs=3).run([work(f"unit-{i}", started.wait) for i in range(3)])

        # The barrier only releases if all three ran concurrently; otherwise
        # this fails on the timeout rather than hanging.
        assert report.ok


class TestFailure:
    def test_fail_fast_cancels_work_not_yet_started(self):
        # Partial state is reported per unit, never silent.
        def boom() -> None:
            raise RuntimeError("nope")

        report = Runner(jobs=1).run([work("a", boom), work("b"), work("c")])

        assert outcomes(report) == [
            Outcome.FAILED,
            Outcome.CANCELLED,
            Outcome.CANCELLED,
        ]
        assert not report.ok

    def test_keep_going_runs_everything_and_still_reports_the_failure(self):
        def boom() -> None:
            raise RuntimeError("nope")

        report = Runner(jobs=1, fail_fast=False).run(
            [work("a", boom), work("b"), work("c")]
        )

        assert outcomes(report) == [Outcome.FAILED, Outcome.DONE, Outcome.DONE]
        assert not report.ok

    def test_a_failure_cancels_only_what_needs_it(self):
        # Arrange
        def boom() -> None:
            raise RuntimeError("nope")

        # Act
        report = Runner(jobs=1, fail_fast=False).run(
            [
                work("a", boom),
                work("b"),
                Work(key="c", label="c", action=lambda: None, needs=("a",)),
                Work(key="d", label="d", action=lambda: None, needs=("c",)),
            ]
        )

        # Assert: d never sees a, but building on what c did not build is the
        # same half-built SDK.
        assert outcomes(report) == [
            Outcome.FAILED,
            Outcome.DONE,
            Outcome.CANCELLED,
            Outcome.CANCELLED,
        ]

    def test_needed_work_finishes_first_even_with_jobs_to_spare(self):
        # Arrange
        seen: list[str] = []
        released = threading.Event()

        def first() -> None:
            released.wait()
            seen.append("a")

        def second() -> None:
            seen.append("b")
            released.set()

        # Act
        report = Runner(jobs=3).run(
            [
                work("a", first),
                work("b", second),
                Work(
                    key="c",
                    label="c",
                    action=lambda: seen.append("c"),
                    needs=("a",),
                ),
            ]
        )

        # Assert
        assert report.ok
        assert seen.index("c") > seen.index("a")

    def test_needing_later_work_is_refused_rather_than_deadlocked(self):
        # Act / Assert
        with pytest.raises(UsageError, match="not earlier work"):
            Runner(jobs=1).run(
                [Work(key="a", label="a", action=lambda: None, needs=("b",)), work("b")]
            )

    def test_the_error_is_kept_for_the_renderer(self):
        def boom() -> None:
            raise RuntimeError("the reason")

        report = Runner(jobs=1).run([work("a", boom)])

        assert str(report.of(Outcome.FAILED)[0].error) == "the reason"

    def test_values_come_back_with_their_unit(self):
        report = Runner(jobs=2).run(
            [
                Work(key="a", label="a", action=lambda: 1),
                Work(key="b", label="b", action=lambda: 2),
            ]
        )

        assert [r.value for r in report.results] == [1, 2]


class TestJobs:
    @pytest.mark.parametrize("jobs", [0, -1])
    def test_a_job_count_below_one_is_a_usage_error(self, jobs: int):
        with pytest.raises(UsageError, match="at least 1"):
            Runner(jobs)
