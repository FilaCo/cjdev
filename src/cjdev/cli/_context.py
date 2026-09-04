from typer import Context
from typer.core import TyperCommand, TyperGroup

from cjdev.bootstrap import Container


class CjdevContext(Context):
    obj: Container


class CjdevGroup(TyperGroup):
    context_class = CjdevContext


class CjdevCommand(TyperCommand):
    context_class = CjdevContext
