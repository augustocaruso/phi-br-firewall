from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """phi-br-presidio-firewall command line."""


@app.command()
def check() -> None:
    """Verify that phi can start."""
    typer.echo("phi baseline ok")
