import importlib.metadata
from typing import Annotated

import typer
from rich import print
from typer import Option


def version_cb(version: bool = False):
    """Handles version option."""
    if version:
        print(f"cjdev {importlib.metadata.version('cjdev')}")
        typer.Exit(0)


VERSION_TYPE_DEF = Annotated[
    bool,
    Option(
        "--version",
        "-V",
        help="Print version info and exit.",
        show_default=False,
        is_eager=True,
        callback=version_cb,
    ),
]
