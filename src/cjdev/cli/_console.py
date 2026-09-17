"""One console, the marks used to say how something ended, and error output.

Plain style strings rather than a `rich` theme, because a theme lives on one
`Console` instance and there are two of them here.
"""

from rich.console import Console
from rich.text import Text

from cjdev.application.runner import Outcome

console = Console()

diagnostics = Console(stderr=True)
"""Where the `-v` transcript, the progress fallback and errors go: they
annotate a command rather than being its output. On stderr so that `--json`
stays a document something else can parse, and so that piping a report never
carries the commands that produced it."""

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


def print_detail(
    console: Console, lines: tuple[str, ...] | list[str], indent: str = ""
) -> None:
    """One line at a time, dim, unwrapped by rich.

    `soft_wrap` so a long path is left to the terminal instead of being
    broken mid-word by rich's own word wrapping.
    """
    for line in lines:
        console.print(f"{indent}{line}", style=DETAIL, highlight=False, soft_wrap=True)


def print_error(message: str) -> None:
    """`error:` in red, the message plain.

    Only the prefix is coloured: the message carries paths, argv and command
    output, and colouring those makes a long failure harder to read rather
    than easier. `highlight=False` keeps rich from picking its own colours out
    of what it thinks are numbers and paths.
    """
    head, _, rest = message.partition("\n")
    # Two spans on an unstyled `Text`, not `Text(style=...)`: a base style
    # applies to everything appended to it, which would paint the whole
    # message red rather than only the word.
    line = Text()
    line.append("error: ", style=FAILED)
    line.append(head)
    diagnostics.print(line, highlight=False, soft_wrap=True)
    if rest:
        diagnostics.print(Text(rest), highlight=False, soft_wrap=True)
