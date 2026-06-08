from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from moodle_loader import __version__
from moodle_loader.builder import PlanBCourseBuilder
from moodle_loader.client import MoodleClient
from moodle_loader.config import Settings
from moodle_loader.exceptions import MoodleError
from moodle_loader.loader import CourseLoader
from moodle_loader.sources import PlanBSource, YamlSource

app = typer.Typer(
    name="moodle-loader",
    help="Load Moodle courses from YAML or Google Sheets.",
    no_args_is_help=True,
)
console = Console()
error_console = Console(stderr=True, style="bold red")


def _filter_specs(specs: list, shortname: str | None) -> list:
    if shortname is None:
        return specs
    filtered = [s for s in specs if s.shortname == shortname]
    if not filtered:
        error_console.print(f"Shortname {shortname!r} not found in source")
        raise typer.Exit(code=1)
    return filtered


def _print_results(results: list, *, verbose: bool = False) -> None:
    from moodle_loader.models import LoadResult

    status_style = {"created": "green", "skipped": "yellow", "failed": "red"}
    table = Table(title="Results", show_lines=False)
    table.add_column("Shortname", style="cyan")
    if verbose:
        table.add_column("Full name")
        table.add_column("Category ID")
        table.add_column("Template ID")
        table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Course ID")
    table.add_column("Message")

    for r in results:
        row = [r.spec.shortname]
        if verbose:
            row += [
                r.spec.fullname,
                str(r.spec.category_id),
                str(r.spec.template_id),
                r.spec.summary[:60] + "…"
                if len(r.spec.summary) > 60
                else r.spec.summary,
            ]
        row += [
            f"[{status_style[r.status]}]{r.status}[/]",
            str(r.course_id) if r.course_id is not None else "-",
            r.message,
        ]
        table.add_row(*row)

    console.print(table)


def _build_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as e:
        error_console.print(f"Invalid configuration: {e}")
        raise typer.Exit(code=2)


def _build_client() -> MoodleClient:
    return MoodleClient(_build_settings())


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
    yaml_path: Path = typer.Argument(
        ..., exists=False, help="Path to the courses YAML file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Do not call the API; validate only"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show all course fields in the results table"
    ),
    shortname: str = typer.Option(
        None, "--shortname", "-s", help="Load only the course with this shortname"
    ),
) -> None:
    """Load courses defined in a YAML file."""
    source = YamlSource(yaml_path)
    specs = _filter_specs(source.load(), shortname)
    client = None if dry_run else _build_client()
    loader = CourseLoader(client=client, dry_run=dry_run)

    try:
        results = loader.load_specs(specs)
    except MoodleError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    _print_results(results, verbose=verbose)

    failed = sum(1 for r in results if r.status == "failed")
    if failed:
        raise typer.Exit(code=1)


@app.command(name="load-sheets")
def load_sheets(
    spreadsheet_id: str = typer.Argument(..., help="Google Spreadsheet ID"),
    worksheet: str = typer.Option(
        None,
        "--worksheet",
        "-w",
        help="Worksheet name (default: SHEETS_WORKSHEET from .env)",
    ),
    credentials_file: str = typer.Option(
        "credentials.json",
        "--credentials-file",
        "-c",
        help="Path to Google Service Account credentials JSON",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Do not call the API; validate only"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show all course fields in the results table"
    ),
    shortname: str = typer.Option(
        None, "--shortname", "-s", help="Load only the course with this shortname"
    ),
    no_writeback: bool = typer.Option(
        False, "--no-writeback", help="Skip writing the Moodle URL back to the Sheet"
    ),
) -> None:
    """Load courses from a Google Sheet."""
    try:
        from moodle_loader.sources.sheets_source import SheetsSource
    except ImportError:
        error_console.print(
            "Google Sheets support not installed. Run: pip install moodle-loader[sheets]"
        )
        raise typer.Exit(code=2)

    settings = Settings()  # type: ignore[call-arg]
    client = MoodleClient(settings)
    source = SheetsSource(
        spreadsheet_id=spreadsheet_id,
        client=client,
        settings=settings,
        worksheet=worksheet or settings.sheets_worksheet,
        credentials_file=credentials_file,
    )
    specs = _filter_specs(source.load(), shortname)
    loader = CourseLoader(client=None if dry_run else client, dry_run=dry_run)

    try:
        results = loader.load_specs(specs)
    except MoodleError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    _print_results(results, verbose=verbose)

    if not dry_run and not no_writeback:
        for r in results:
            if r.status == "created" and r.course_id is not None:
                url = f"{settings.moodle_url}/course/view.php?id={r.course_id}"
                source.write_moodle_link(r.spec.shortname, url)

    failed = sum(1 for r in results if r.status == "failed")
    if failed:
        raise typer.Exit(code=1)


@app.command(name="import-planb")
def import_planb(
    course_path: Path = typer.Argument(
        ..., help="Path to the Plan \u20bf course directory"
    ),
    shortname: str = typer.Option(
        None, "--shortname", help="Override default shortname (directory name)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Parse and validate without calling Moodle"
    ),
    visible: bool = typer.Option(
        False, "--visible", help="Create course as visible (default: hidden)"
    ),
) -> None:
    """Import a Plan \u20bf course from a local directory into Moodle.

    WARNING: existing course with the same shortname will be deleted before import.
    """
    from moodle_loader.exceptions import SourceError

    if not course_path.exists():
        error_console.print(f"Path does not exist: {course_path}")
        raise typer.Exit(code=1)
    if not course_path.is_dir():
        error_console.print(f"Path is not a directory: {course_path}")
        raise typer.Exit(code=1)

    try:
        spec = PlanBSource(course_path).load()
    except SourceError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    if shortname:
        spec = spec.model_copy(update={"default_shortname": shortname})

    total_chapters = sum(len(p.chapters) for p in spec.parts)

    if dry_run:
        from rich.panel import Panel
        from rich.table import Table

        summary_preview = (
            spec.summary[:80] + "\u2026" if len(spec.summary) > 80 else spec.summary
        )

        console.print()
        console.print(
            Panel(
                f"[bold]{spec.fullname}[/bold]\n"
                f"[dim]shortname:[/dim] {spec.default_shortname}\n"
                f"[dim]summary:[/dim]  {summary_preview}",
                title="[cyan]Plan \u20bf Course[/cyan]",
                expand=False,
            )
        )

        stats = Table.grid(padding=(0, 2))
        stats.add_column(style="dim")
        stats.add_column(style="bold")
        stats.add_row("Parts", str(len(spec.parts)))
        stats.add_row("Chapters", str(total_chapters))
        stats.add_row("Assets", str(len(spec.assets)))
        console.print(stats)
        console.print()

        parts_table = Table(title="Parts", show_lines=False)
        parts_table.add_column("#", style="dim", width=3)
        parts_table.add_column("Title", style="cyan")
        parts_table.add_column("Chapters", justify="right")
        for i, part in enumerate(spec.parts, 1):
            parts_table.add_row(str(i), part.title, str(len(part.chapters)))
        console.print(parts_table)
        console.print()
        console.print(
            "[green]\u2713[/green] Dry run complete \u2013 no Moodle calls made."
        )
        console.print()
        return

    settings = _build_settings()
    client = MoodleClient(settings)
    # Registry of sibling courses so cross-course planb.academy links can be
    # rewritten to internal Moodle URLs.
    from moodle_loader.sources.planb_source import build_course_uuid_map

    course_uuid_map = build_course_uuid_map(course_path.resolve().parent)
    builder = PlanBCourseBuilder(
        client,
        spec,
        visible=visible,
        category_name=settings.default_category_name,
        course_uuid_map=course_uuid_map,
    )
    try:
        result = builder.build()
    except MoodleError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    from rich.table import Table

    table = Table(title=f"Imported: {spec.fullname}", show_lines=False)
    table.add_column("Field", style="dim")
    table.add_column("Value", style="cyan")
    table.add_row("Course ID", str(result.course_id))
    table.add_row("Shortname", spec.default_shortname)
    table.add_row("Sections created", str(len(result.sections_created)))
    table.add_row("Pages created", str(len(result.pages_created)))
    table.add_row("Assets uploaded", str(result.assets_uploaded))
    table.add_row("Previous course wiped", "yes" if result.wiped else "no")
    console.print(table)


@app.command(name="download-videos")
def download_videos(
    courses_root: Path = typer.Argument(
        None, help="Root directory containing Plan ₿ course directories"
    ),
    course: Path = typer.Option(
        None, "--course", help="A single Plan ₿ course directory to download"
    ),
    manifest: Path = typer.Option(
        Path("video_manifest.yml"), "--manifest", help="Path to the video manifest"
    ),
    archive_dir: Path = typer.Option(
        Path("videos"), "--archive-dir", help="Directory to store downloaded MP4s"
    ),
    lang: str = typer.Option("en", "--lang", help="Language track to download"),
    force: bool = typer.Option(
        False, "--force", help="Re-download videos already in the manifest"
    ),
    only: list[str] = typer.Option(
        None, "--only", help="Limit to these Plan ₿ video UUIDs (repeatable)"
    ),
) -> None:
    """Download Plan ₿ PeerTube course videos to local MP4s (English only).

    Pass a courses root to scan every course, or --course to scan a single
    course directory.
    """
    from moodle_loader.videos.downloader import VideoDownloader
    from moodle_loader.videos.ffmpeg import FfmpegError, check_ffmpeg
    from moodle_loader.videos.manifest import VideoManifest

    if lang != "en":
        error_console.print("Only --lang en is supported in this version.")
        raise typer.Exit(code=1)
    if course is not None and courses_root is not None:
        error_console.print("Pass either a courses root or --course, not both.")
        raise typer.Exit(code=1)
    target = course or courses_root
    if target is None:
        error_console.print("Provide a courses root path or --course <course dir>.")
        raise typer.Exit(code=1)
    if not target.is_dir():
        error_console.print(f"Not a directory: {target}")
        raise typer.Exit(code=1)
    try:
        check_ffmpeg()
    except FfmpegError as e:
        error_console.print(str(e))
        raise typer.Exit(code=1)

    downloader = VideoDownloader(
        target, VideoManifest.load(manifest), archive_dir, lang=lang
    )
    result = downloader.run(force=force, only=only or None)

    table = Table(title="Video download", show_lines=False)
    table.add_column("Outcome", style="dim")
    table.add_column("Count", justify="right", style="cyan")
    table.add_row("Downloaded", str(len(result.downloaded)))
    table.add_row("Skipped", str(len(result.skipped)))
    table.add_row("Failed", str(len(result.failed)))
    console.print(table)

    if result.downloaded:
        console.print("\n[green]Saved videos:[/green]")
        for uuid in result.downloaded:
            entry = downloader.manifest.entries.get(uuid)
            if entry and entry.mp4:
                path = (downloader.manifest.path.parent / entry.mp4).resolve()
                # soft_wrap + markup=False so long paths aren't folded mid-string
                # or misread as Rich markup.
                console.print(f"  {path}", markup=False, soft_wrap=True, highlight=False)

    if result.failed:
        error_console.print(f"{len(result.failed)} video(s) failed: {result.failed}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
