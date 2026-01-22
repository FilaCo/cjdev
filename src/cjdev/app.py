from typer import Typer

from cjdev.features.build import app as build_app
from cjdev.features.dc import app as dc_app
from cjdev.features.git import app as git_app
from cjdev.features.init import app as init_app
from cjdev.features.status import app as status_app
from cjdev.features.test import app as test_app

cjdev = Typer()

cjdev.add_typer(status_app)
cjdev.add_typer(init_app)
cjdev.add_typer(build_app)
cjdev.add_typer(test_app)
cjdev.add_typer(git_app)
cjdev.add_typer(dc_app)
