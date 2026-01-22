from typer import Typer

app = Typer()


@app.command()
def dc():
    """Execute a command in the container"""
    pass
