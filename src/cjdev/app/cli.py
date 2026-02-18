from .container import CjDevContainer
from .entrypoints import cli


def run_cjdev() -> None:
    container = CjDevContainer()
    container.wire(modules=[__name__])
    cli()
