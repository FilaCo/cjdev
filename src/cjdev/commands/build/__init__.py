from cjdev.commands.build.context import BuildType, BuildContext
from typing import Annotated
from .subcommands.cjc import cli as cjc_cli
from .subcommands.rt import cli as rt_cli
from .subcommands.sdk import cli as sdk_cli, build_sdk
from .subcommands.std import cli as std_cli
from .subcommands.stdx import cli as stdx_cli


from typer import Context, Typer, Option

cli = Typer()
cli.add_typer(cjc_cli)
cli.add_typer(rt_cli)
cli.add_typer(sdk_cli)
cli.add_typer(std_cli)
cli.add_typer(stdx_cli)


BUILD_TYPE_DEF = Annotated[
    BuildType,
    Option(
        "--build-type",
        "-t",
        help="Build type.",
    ),
]


@cli.callback(invoke_without_command=True)
def build_cb(ctx: Context, build_type: BUILD_TYPE_DEF = BuildType.RELEASE):
    ctx.obj = BuildContext(global_ctx=ctx.obj, build_type=build_type)
    if not ctx.invoked_subcommand:
        ctx.invoke(build_sdk)
