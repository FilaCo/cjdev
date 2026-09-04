"""The display may be concurrent; the transcript may not be (PAR-4)."""

from io import StringIO

from rich.console import Console

from cjdev.application.runner import Outcome, Runner, Work
from cjdev.cli._progress import ConsoleProgress


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
        # A pipe or a CI log gets the summary and nothing else: an animation
        # redrawn 12 times a second is noise once it is not being watched.
        console, sink = quiet_console()
        progress = ConsoleProgress(console)
        progress.track(["a", "b"])

        with progress:
            progress.started("a")
            progress.finished("a", Outcome.DONE)

        assert sink.getvalue() == ""

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
