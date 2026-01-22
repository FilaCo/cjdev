from typer import Typer

app = Typer()


@app.command()
def status():
    """Show cjdev environment status"""
    pass
