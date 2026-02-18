import logging
import shutil
from pathlib import Path
from typing import Annotated

from typer import Context, Exit, Option, Typer

from cjdev.commands.build.context import BuildContext
from cjdev.shared.proc import Process, run_many

logger = logging.getLogger(__name__)
cli = Typer()


@cli.command()
@cli.command("compiler", hidden=True)
def cjc(
    ctx: Context,
    no_tests: Annotated[
        bool,
        Option(
            "--no-tests",
            help="Build cjc without unittests.",
        ),
    ] = True,
):
    """Build compiler."""
    build_ctx = ctx.ensure_object(BuildContext)
    _cjc(build_ctx, no_tests)


def _cjc(ctx: BuildContext, no_tests: bool):
    cfg_cjc = ctx.global_ctx.cfg.projects.cangjie_compiler
    if not cfg_cjc:
        logger.error("Cangjie compiler config is missing.")
        raise Exit(1)

    root = ctx.global_ctx.home.parent
    cwd = Path(cfg_cjc.path)
    cwd = cwd if cwd.is_absolute() else root / cwd
    build_proc = Process(args=ctx.make_common_build_args(), cwd=cwd.as_posix())

    install_proc = Process(args=ctx.make_common_install_args(), cwd=cwd.as_posix())
    run_many([build_proc, install_proc])
    shutil.copytree(cwd / "output", root / "dist")
