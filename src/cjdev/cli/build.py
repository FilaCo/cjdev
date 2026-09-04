from typer import Typer

from ._context import CjdevCommand, CjdevContext, CjdevGroup

cli = Typer(cls=CjdevGroup)


@cli.command(name="compiler", cls=CjdevCommand)
def build_compiler(ctx: CjdevContext) -> None:
    """Build Cangjie compiler."""
    pass


@cli.command(name="runtime", cls=CjdevCommand)
def build_runtime(ctx: CjdevContext) -> None:
    """Build Cangjie runtime."""
    pass


@cli.command(name="stdlib", cls=CjdevCommand)
def build_stdlib(ctx: CjdevContext) -> None:
    """Build Cangjie standard library."""
    pass


@cli.command(name="stdx", cls=CjdevCommand)
def build_stdx(ctx: CjdevContext) -> None:
    """Build Cangjie standard library extensions (stdx)."""
    pass


@cli.command(name="cjpm", cls=CjdevCommand)
def build_cjpm(ctx: CjdevContext) -> None:
    """Build Cangjie package manager (cjpm)."""
    pass


@cli.command(name="cjfmt", cls=CjdevCommand)
def build_cjfmt(ctx: CjdevContext) -> None:
    """Build Cangjie formatter (cjfmt)."""
    pass


@cli.command(name="cjlint", cls=CjdevCommand)
def build_cjlint(ctx: CjdevContext) -> None:
    """Build Cangjie linter (cjlint)."""
    pass


@cli.command(name="cjcov", cls=CjdevCommand)
def build_cjcov(ctx: CjdevContext) -> None:
    """Build Cangjie coverage tool (cjcov)."""
    pass


@cli.command(name="cjtrace-recover", cls=CjdevCommand)
def build_cjtrace_recover(ctx: CjdevContext) -> None:
    """Build Cangjie exception stack restoration tool (cjtrace-recover)."""
    pass


@cli.command(name="hyprlang-extension", cls=CjdevCommand)
def build_hyprlang_extension(ctx: CjdevContext) -> None:
    """Build Cangjie HyperLangExtension."""
    pass


@cli.command(name="cjls", cls=CjdevCommand)
def build_cjls(ctx: CjdevContext) -> None:
    """Build Cangjie language server (LSPServer, LSPMacroServer)."""
    pass


@cli.command(name="cjprof", cls=CjdevCommand)
def build_cjprof(ctx: CjdevContext) -> None:
    """Build Cangjie profiler (cjprof)."""
    pass


@cli.command(name="cjcompat", cls=CjdevCommand)
def build_cjcompat(ctx: CjdevContext) -> None:
    """Build Cangjie cjcompat."""
    pass
