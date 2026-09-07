"""The display may be concurrent; the transcript may not be."""

from io import StringIO

from rich.console import Console

from cjdev.application.runner import Outcome, Runner, Work
from cjdev.cli._progress import ConsoleProgress, format_duration


def quiet_console() -> tuple[Console, StringIO]:
    sink = StringIO()
    return Console(file=sink, force_terminal=False), sink


class TestOutputCapture:
    def test_a_units_output_is_attributed_to_it(self):
        progress = ConsoleProgress(quiet_console()[0])

        def speak(label: str) -> None:
            progress.emit(f"from {label}")

        Runner(jobs=4).run(
            [
                Work(key=n, label=n, action=lambda n=n: speak(n))
                for n in ("a", "b", "c")
            ],
            observer=progress,
        )

        # Attribution survives concurrency because `started` arrives on the
        # worker's own thread, which is what binds the buffer to it.
        assert progress.lines("a") == ("from a",)
        assert progress.lines("b") == ("from b",)
        assert progress.lines("c") == ("from c",)

    def test_output_is_never_printed_as_it_happens(self):
        console, sink = quiet_console()
        progress = ConsoleProgress(console)
        progress.track(["a"])

        Runner(jobs=1).run(
            [Work(key="a", label="a", action=lambda: progress.emit("secret"))],
            observer=progress,
        )

        assert "secret" not in sink.getvalue()


class TestDisplay:
    def test_nothing_is_drawn_without_a_terminal(self):
        # A pipe or a CI log gets no animation: 12 redraws a second is control
        # codes once it is not being watched.
        console, sink = quiet_console()
        progress = ConsoleProgress(console)
        progress.track(["a", "b"])

        with progress:
            progress.started("a")
            progress.finished("a", Outcome.DONE)

        assert sink.getvalue() == ""

    def test_without_a_terminal_a_fallback_still_reports_each_unit(self):
        # Otherwise a CI log shows nothing at all for the ten minutes a clone
        # takes, which reads as a hang.
        console, _ = quiet_console()
        fallback, seen = quiet_console()
        progress = ConsoleProgress(console, fallback=fallback)
        progress.track(["a", "b"])

        with progress:
            for label in ("a", "b"):
                progress.started(label)
                progress.finished(label, Outcome.DONE)

        assert "[1/2] a" in seen.getvalue()
        assert "[2/2] b" in seen.getvalue()

    def test_rows_keep_their_given_order_whatever_finishes_first(self):
        sink = StringIO()
        console = Console(file=sink, force_terminal=True, width=40)
        progress = ConsoleProgress(console)
        progress.track(["first", "second"])

        with progress:
            progress.started("second")
            progress.finished("second", Outcome.DONE)
            progress.started("first")
            progress.finished("first", Outcome.FAILED)

        drawn = sink.getvalue()
        assert drawn.index("first") < drawn.index("second")

    def test_the_current_step_is_shown_against_the_running_unit(self):
        sink = StringIO()
        console = Console(file=sink, force_terminal=True, width=70)
        progress = ConsoleProgress(console)
        progress.track(["alpha"], title="Fetching")

        with progress:
            progress.started("alpha")
            progress.step("fetching from upstream")

        drawn = sink.getvalue()
        assert "fetching from upstream" in drawn
        assert "Fetching" in drawn

    def test_a_step_outside_any_unit_is_dropped_rather_than_misattributed(self):
        # `step` reads the thread-local a worker sets; on the main thread
        # there is no unit it could belong to.
        progress = ConsoleProgress(quiet_console()[0])
        progress.track(["a"])

        progress.step("from nowhere")

        assert "from nowhere" not in str(progress.__rich__())


class TestEstimate:
    def test_no_estimate_until_something_has_finished(self):
        sink = StringIO()
        console = Console(file=sink, force_terminal=True, width=70)
        progress = ConsoleProgress(console)
        progress.track(["a", "b"], jobs=1)

        with progress:
            progress.started("a")

        assert "left" not in sink.getvalue()

    def test_the_headline_counts_what_is_done_against_the_total(self):
        sink = StringIO()
        console = Console(file=sink, force_terminal=True, width=70)
        progress = ConsoleProgress(console)
        progress.track(["a", "b"])

        with progress:
            progress.started("a")
            progress.finished("a", Outcome.DONE)

        assert "1/2 done" in sink.getvalue()

    def test_the_summary_names_every_outcome_it_saw(self):
        progress = ConsoleProgress(quiet_console()[0])
        progress.track(["a", "b", "c"])

        with progress:
            progress.finished("a", Outcome.DONE)
            progress.finished("b", Outcome.FAILED)
            progress.finished("c", Outcome.CANCELLED)

        assert progress.summary().startswith("1 done, 1 failed, 1 cancelled in ")


class TestDurations:
    def test_seconds_keep_a_decimal_while_they_are_the_whole_answer(self):
        assert format_duration(0.0) == "0.0s"
        assert format_duration(8.42) == "8.4s"

    def test_minutes_drop_it(self):
        assert format_duration(65) == "1m 05s"
        assert format_duration(600) == "10m 00s"
