from cjdev.cli import cli
from cjdev.cli._console import print_error
from cjdev.errors import CjdevError


def main() -> None:
    """Entry point: turns a reported error into a message and an exit code.

    A traceback reaching the user is a defect; the code says which kind of
    failure it was.
    """
    try:
        cli()
    except CjdevError as exc:
        print_error(str(exc))
        raise SystemExit(exc.exit_code) from exc
    except KeyboardInterrupt:
        # Ctrl-C at a prompt, or between phases. A fan-out reports its own
        # interruption per unit; this is the case where nothing was running.
        print_error("interrupted.")
        raise SystemExit(1) from None
