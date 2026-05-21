from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from moodle_loader import __version__
from moodle_loader.client import MoodleClient
from moodle_loader.config import Settings
from moodle_loader.exceptions import MoodleError
from moodle_loader.loader import CourseLoader
from moodle_loader.sources import YamlSource

app = typer.Typer(
    name="moodle-loader",
    help="Load Moodle courses from YAML or Google Sheets.",
    no_args_is_help=True,
)
console = Console()
error_console = Console(stderr=True, style="bold red")


def _build_client() -> MoodleClient:
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as e:
        error_console.print(f"Invalid configuration: {e}")
        raise typer.Exit(code=2)
    return MoodleClient(settings)


@app.command()
def version() -> None:
    """Show the installed version."""
    console.print(f"moodle-loader {__version__}")


@app.command()
def info() -> None:
    """Verify connection and token against Moodle."""
    client = _build_client()
    try:
        data = client.site_info()
    except MoodleError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    console.print(f"[green]✓[/green] Connected to {data.get('sitename')}")
    console.print(f"  User: {data.get('fullname')} ({data.get('username')})")
    console.print(f"  Enabled functions: {len(data.get('functions', []))}")


@app.command()
def load(
    yaml_path: Path = typer.Argument(..., exists=False, help="Path to the courses YAML file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not call the API; validate only"),
) -> None:
    """Load courses defined in a YAML file."""
    source = YamlSource(yaml_path)
    client = None if dry_run else _build_client()
    loader = CourseLoader(client=client, dry_run=dry_run)

    try:
        results = loader.load(source)
    except MoodleError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    table = Table(title="Results", show_lines=False)
    table.add_column("Shortname", style="cyan")
    table.add_column("Status")
    table.add_column("Course ID")
    table.add_column("Message")

    status_style = {"created": "green", "skipped": "yellow", "failed": "red"}
    for r in results:
        table.add_row(
            r.spec.shortname,
            f"[{status_style[r.status]}]{r.status}[/]",
            str(r.course_id) if r.course_id is not None else "-",
            r.message,
        )
    console.print(table)

    failed = sum(1 for r in results if r.status == "failed")
    if failed:
        raise typer.Exit(code=1)


@app.command(name="load-sheets")
def load_sheets(
    spreadsheet_id: str = typer.Argument(..., help="Google Spreadsheet ID"),
    worksheet: str = typer.Option("Sheet1", "--worksheet", "-w", help="Worksheet name"),
    credentials_file: str = typer.Option("credentials.json", "--credentials-file", "-c", help="Path to Google Service Account credentials JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not call the API; validate only"),
) -> None:
    """Load courses from a Google Sheet."""
    try:
        from moodle_loader.sources.sheets_source import SheetsSource
    except ImportError:
        error_console.print("Google Sheets support not installed. Run: pip install moodle-loader[sheets]")
        raise typer.Exit(code=2)

    settings = Settings()  # type: ignore[call-arg]
    client = MoodleClient(settings)
    source = SheetsSource(
        spreadsheet_id=spreadsheet_id,
        client=client,
        settings=settings,
        worksheet=worksheet,
        credentials_file=credentials_file,
    )
    loader = CourseLoader(client=None if dry_run else client, dry_run=dry_run)

    try:
        results = loader.load(source)
    except MoodleError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    table = Table(title="Results", show_lines=False)
    table.add_column("Shortname", style="cyan")
    table.add_column("Status")
    table.add_column("Course ID")
    table.add_column("Message")

    status_style = {"created": "green", "skipped": "yellow", "failed": "red"}
    for r in results:
        table.add_row(
            r.spec.shortname,
            f"[{status_style[r.status]}]{r.status}[/]",
            str(r.course_id) if r.course_id is not None else "-",
            r.message,
        )
    console.print(table)

    failed = sum(1 for r in results if r.status == "failed")
    if failed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
