from cjdev.cli import cli
from cjdev.cli._output import current
from cjdev.errors import AbortedError, CjdevError


def main() -> None:
    """Entry point: turns a reported error into a message and an exit code.

    A traceback reaching the user is a defect; the code says which kind of
    failure it was. How it is rendered - a line on stderr, or the same failure
    inside the `--json` envelope - is the command's choice, made before it
    could fail and read back here.
    """
    try:
        cli()
    except CjdevError as exc:
        current().failure(exc)
        raise SystemExit(exc.exit_code) from exc
    except KeyboardInterrupt:
        # Ctrl-C at a prompt, or between phases. A fan-out reports its own
        # interruption per unit; this is the case where nothing was running.
        current().failure(AbortedError("interrupted"))
        raise SystemExit(1) from None
