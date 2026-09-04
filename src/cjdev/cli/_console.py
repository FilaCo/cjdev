"""One console, and the marks used to say how something ended.

Plain style strings rather than a `rich` theme, because a theme lives on one
`Console` instance
"""

from rich.console import Console

from cjdev.application.runner import Outcome

console = Console()

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
