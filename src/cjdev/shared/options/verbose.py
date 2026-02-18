from typing import Annotated

from typer import Option

VERBOSE_TYPE_DEF = Annotated[
    bool,
    Option(
        "--verbose",
        "-v",
        help="Use verbose output.",
        show_default=False,
        is_eager=True,
    ),
]
