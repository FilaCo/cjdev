"""One console, and the marks used to say how something ended.

Plain style strings rather than a `rich` theme, because a theme lives on one
`Console` instance
"""

from rich.console import Console

from cjdev.application.runner import Outcome

console = Console()

diagnostics = Console(stderr=True)
"""Where the `-v` transcript goes: it annotates a command rather than being
its output. On stderr so that `--json` stays a document something else can
parse (UX-6), and so that piping a report never carries the commands that
produced it."""

OK = "green"
FAILED = "bold red"
CANCELLED = "yellow"
DETAIL = "dim"
RUNNING = "cyan"

MARKS: dict[Outcome, tuple[str, str]] = {
    Outcome.DONE: ("✓", OK),
    Outcome.FAILED: ("✗", FAILED),
    Outcome.CANCELLED: ("-", CANCELLED),
}

WAITING = ("·", DETAIL)
