import sys

from cjdev.cli import cli
from cjdev.errors import CjdevError


def main() -> None:
    """Entry point: turns a reported error into a message and an exit code.

    A traceback reaching the user is a defect (UX-4); the code says which kind
    of failure it was (UX-5).
    """
    try:
        cli()
    except CjdevError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(exc.exit_code) from exc
