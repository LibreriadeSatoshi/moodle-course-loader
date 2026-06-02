from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path

from markdown_it import MarkdownIt

from moodle_loader.client import MoodleClient
from moodle_loader.models import PlanBBuildResult, PlanBCourseSpec

# Module-level singletons.
# The CommonMark preset leaves the GFM ``table`` rule disabled, so Plan ₿
# bodies using pipe-table syntax (e.g. the Bitcoin halving table) would render
# as a raw ``<p>``. Enable it so those tables become proper ``<table>`` markup.
_MD = MarkdownIt().enable("table")
_PLAN_B_TAG_RE = re.compile(r"</?(?:partId|chapterId)[^>]*>")
_ASSET_IMG_RE = re.compile(r"!\[([^\]]*)\]\((assets/en/[^)]+)\)")
_INTRO_ASSET_RE = re.compile(r"!\[[^\]]*\]\((assets/en/[^)]+)\)")
# Matches an opening <img> tag that doesn't already carry a style attribute.
_IMG_TAG_RE = re.compile(r"<img(?![^>]*\bstyle=)", re.IGNORECASE)
# Constrains images to the page width (so large source files don't overflow),
# forces them onto their own line via ``display: block`` (text resumes below
# rather than wrapping beside the image), and centers them with ``margin: auto``.
_RESPONSIVE_IMG_STYLE = (
    "display: block; margin: 1em auto; max-width: 75%; height: auto;"
)

# markdown-it emits bare <table>/<th>/<td> tags. Moodle stores the page HTML
# verbatim and its theme draws no cell borders by default, so tables looked
# borderless. We inject inline styles (Moodle strips <style> blocks but keeps
# inline ``style`` attributes) to make the grid visible. Column alignment adds
# a ``text-align`` style to cells, so we merge rather than overwrite.
_TABLE_STYLE = "border-collapse: collapse; margin: 1em 0;"
_CELL_STYLE = "border: 1px solid #ccc; padding: 0.4em 0.6em;"
_HEADER_CELL_STYLE = _CELL_STYLE + " background-color: #f2f2f2;"
_STYLE_ATTR_RE = re.compile(r'style="([^"]*)"', re.IGNORECASE)

# planb.academy links. Course links carry the course UUID (and optionally a
# language prefix like /en/ or /zh-Hans/ and a deep /chapterUuid suffix); the
# course UUID is captured so it can be mapped to an internal Moodle course.
_PLANB_COURSE_RE = re.compile(
    r"https?://planb\.academy/(?:[A-Za-z]{2,3}(?:-[A-Za-z]+)?/)?"
    r"courses/([0-9a-fA-F-]{36})(?:/[0-9a-fA-F-]{36})?"
)
# Any planb.academy URL (used to strip non-course links: tutorials, glossary…).
_PLANB_ANY_RE = re.compile(r"https?://planb\.academy/\S*")
# A markdown link [label](planb-url).
_PLANB_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://planb\.academy/[^)]+)\)")

log = logging.getLogger(__name__)


def _rewrite_planb_links(text: str, link_map: dict[str, str]) -> str:
    """Rewrite planb.academy links in a markdown body.

    * Course links whose UUID is in *link_map* become the mapped internal Moodle
      URL (a deep ``/chapterUuid`` suffix is dropped — it points at the course).
    * Every other planb.academy link is removed: the ``[label](url)`` form keeps
      its ``label``; a bare URL is dropped entirely.
    """

    def _md_repl(m: re.Match) -> str:  # type: ignore[type-arg]
        label, url = m.group(1), m.group(2)
        course = _PLANB_COURSE_RE.fullmatch(url)
        if course:
            target = link_map.get(course.group(1))
            if target:
                return f"[{label}]({target})"
        return label  # non-course or unresolved → keep the link text only

    # 1. Markdown links first, so their URLs aren't caught by the bare passes.
    text = _PLANB_MD_LINK_RE.sub(_md_repl, text)

    # 2. Bare course URLs: resolvable → autolink (clickable), else drop.
    def _course_repl(m: re.Match) -> str:  # type: ignore[type-arg]
        target = link_map.get(m.group(1))
        return f"<{target}>" if target else ""

    text = _PLANB_COURSE_RE.sub(_course_repl, text)

    # 3. Any remaining bare planb.academy URL (tutorials, glossary, unknown) → drop.
    return _PLANB_ANY_RE.sub("", text)


def _inject_style(html: str, tag: str, style: str) -> str:
    """Add *style* to every opening *tag*, merging into an existing attribute."""
    open_re = re.compile(rf"<{tag}\b([^>]*)>", re.IGNORECASE)

    def _repl(m: re.Match) -> str:  # type: ignore[type-arg]
        attrs = m.group(1)
        existing = _STYLE_ATTR_RE.search(attrs)
        if existing:
            merged = f"{existing.group(1).rstrip().rstrip(';')}; {style}"
            attrs = attrs[: existing.start(1)] + merged + attrs[existing.end(1) :]
            return f"<{tag}{attrs}>"
        return f'<{tag} style="{style}"{attrs}>'

    return open_re.sub(_repl, html)


def _render_html(
    body: str,
    asset_url_map: dict[str, str],
    link_map: dict[str, str] | None = None,
) -> str:
    """Render a Plan ₿ markdown body to HTML suitable for a Moodle page.

    Steps:
    1. Strip Plan ₿ XML tags (<partId>, <chapterId>, and their closing forms).
    2. Rewrite ``![alt](assets/en/fname)`` references using *asset_url_map*.
    3. Rewrite planb.academy links: known course links → internal Moodle URLs
       (via *link_map*, keyed by course UUID), other planb links stripped.
    4. Convert the resulting markdown to HTML via markdown-it-py.
    5. Constrain images to the page width so large source files don't
       overflow the Moodle page layout.
    6. Add inline borders/padding to tables so they render as a visible grid
       (Moodle's theme draws none by default).
    """
    content = _PLAN_B_TAG_RE.sub("", body)

    def _replace_asset(m: re.Match) -> str:  # type: ignore[type-arg]
        alt = m.group(1)
        path = m.group(2)
        url = asset_url_map.get(path, f"@@PLUGINFILE@@/{path.split('/')[-1]}")
        return f"![{alt}]({url})"

    content = _ASSET_IMG_RE.sub(_replace_asset, content)
    content = _rewrite_planb_links(content, link_map or {})
    html = _MD.render(content)
    html = _IMG_TAG_RE.sub(f'<img style="{_RESPONSIVE_IMG_STYLE}"', html)
    html = _inject_style(html, "table", _TABLE_STYLE)
    html = _inject_style(html, "th", _HEADER_CELL_STYLE)
    html = _inject_style(html, "td", _CELL_STYLE)
    return html


class PlanBCourseBuilder:
    """Builds a Moodle course from a :class:`~moodle_loader.models.PlanBCourseSpec`."""

    def __init__(
        self,
        client: MoodleClient,
        spec: PlanBCourseSpec,
        *,
        visible: bool = False,
        category_name: str = "Miscellaneous",
        course_uuid_map: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self._spec = spec
        self._visible = visible
        self._category_name = category_name
        # {planb_course_uuid → shortname} across all sibling courses, used to
        # rewrite cross-course links to internal Moodle URLs.
        self._course_uuid_map = course_uuid_map or {}
        # Set in _create_course; used by later steps that need the Moodle course id.
        self._course_id: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> PlanBBuildResult:
        """Orchestrates: wipe → create → upload assets → set image → sections → pages."""
        wiped = self._wipe_existing()
        category_id = self._resolve_category()
        course_id = self._create_course(category_id)
        asset_url_map = self._build_asset_url_map()
        link_map = self._build_link_map()
        self._set_course_image()
        sections_created = self._create_sections()
        pages_created = self._create_pages(asset_url_map, link_map)
        return PlanBBuildResult(
            course_id=course_id,
            sections_created=sections_created,
            pages_created=pages_created,
            assets_uploaded=len(asset_url_map),  # counts assets embedded as data URIs
            wiped=wiped,
        )

    # ------------------------------------------------------------------
    # Build steps
    # ------------------------------------------------------------------

    def _wipe_existing(self) -> bool:
        """Delete the existing course if its shortname is already taken.

        Returns ``True`` if a course was deleted, ``False`` otherwise.
        Propagates any :class:`~moodle_loader.exceptions.MoodleAPIError` raised
        by the client.
        """
        existing = self._client.get_course_by_shortname(self._spec.default_shortname)
        if existing is None:
            log.debug(
                "No existing course for shortname %r", self._spec.default_shortname
            )
            return False
        course_id = existing["id"]
        log.info(
            "Wiping existing course id=%d (shortname=%r)",
            course_id,
            self._spec.default_shortname,
        )
        self._client.delete_course(course_id)
        return True

    def _resolve_category(self) -> int:
        """Return the Moodle category id matching *category_name*.

        Falls back to ``1`` with a warning when no match is found.
        """
        categories = self._client.get_categories()
        for cat in categories:
            if cat.get("name") == self._category_name:
                cat_id = int(cat["id"])
                log.debug("Resolved category %r → id=%d", self._category_name, cat_id)
                return cat_id
        log.warning(
            "Category %r not found in Moodle; falling back to categoryid=1",
            self._category_name,
        )
        return 1

    def _create_course(self, category_id: int) -> int:
        """Create the Moodle course and return its id."""
        numsections = len(self._spec.parts)
        result = self._client.create_course(
            fullname=self._spec.fullname,
            shortname=self._spec.default_shortname,
            categoryid=category_id,
            summary=self._spec.summary,
            visible=self._visible,
            numsections=numsections,
        )
        self._course_id = int(result["id"])
        log.info(
            "Created course id=%d shortname=%r",
            self._course_id,
            self._spec.default_shortname,
        )
        return self._course_id

    def _referenced_course_uuids(self) -> set[str]:
        """Course UUIDs linked from this spec's intro and chapter bodies."""
        uuids: set[str] = set()
        bodies = [self._spec.intro] + [
            ch.body for part in self._spec.parts for ch in part.chapters
        ]
        for body in bodies:
            uuids.update(m.group(1) for m in _PLANB_COURSE_RE.finditer(body))
        return uuids

    def _build_link_map(self) -> dict[str, str]:
        """Build ``{planb_uuid → internal Moodle course URL}`` for this course.

        Only UUIDs actually referenced *and* known in the course registry are
        resolved. The current course resolves to its own freshly-created id;
        others are looked up by shortname. A target that doesn't exist in Moodle
        yet can't be resolved to a numeric id, so it's left out (its links get
        stripped) — re-running the import once all courses exist resolves them.
        """
        link_map: dict[str, str] = {}
        for uuid in self._referenced_course_uuids():
            shortname = self._course_uuid_map.get(uuid)
            if shortname is None:
                continue  # not a course we're migrating → link stripped
            if uuid == self._spec.planb_id:
                course_id: int | None = self._course_id
            else:
                existing = self._client.get_course_by_shortname(shortname)
                course_id = existing["id"] if existing else None
            if course_id is None:
                log.warning(
                    "Course %r (uuid=%s) not in Moodle yet; stripping its links. "
                    "Re-run the import once it exists to resolve them.",
                    shortname,
                    uuid,
                )
                continue
            link_map[uuid] = f"{self._client.base_url}/course/view.php?id={course_id}"
        return link_map

    def _build_asset_url_map(self) -> dict[str, str]:
        """Build ``{relative_path → data_uri}`` for every asset in the spec.

        ``local_moodlecourseloader_create_page`` stores content as raw HTML
        without a Moodle file area, so images must be embedded as data URIs
        to display correctly inside Moodle pages.
        """
        if not self._spec.assets:
            return {}

        result: dict[str, str] = {}
        for asset in self._spec.assets:
            filename = Path(asset.relative_path).name
            mime, _ = mimetypes.guess_type(filename)
            if not mime:
                # Explicit fallback for types missing in older Python versions
                ext = Path(filename).suffix.lower()
                mime = {
                    ".webp": "image/webp",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".svg": "image/svg+xml",
                }.get(ext, "application/octet-stream")
            b64 = base64.b64encode(asset.absolute_path.read_bytes()).decode("ascii")
            result[asset.relative_path] = f"data:{mime};base64,{b64}"
            log.debug("Embedded asset %r as data URI (%s)", filename, mime)

        log.info("Built data URIs for %d asset(s)", len(result))
        return result

    def _set_course_image(self) -> None:
        """Send the course cover image to Moodle as base64.

        Scans ``spec.intro`` for the first ``![alt](assets/en/<fname>)``
        reference and calls
        :meth:`~moodle_loader.client.MoodleClient.set_course_image` with the
        raw bytes base64-encoded.

        Skipped entirely when either ``spec.assets`` is empty or ``spec.intro``
        contains no matching asset reference.
        """
        if not self._spec.assets or not self._spec.intro:
            return

        m = _INTRO_ASSET_RE.search(self._spec.intro)
        if m is None:
            log.debug("No asset reference in intro; skipping set_course_image")
            return

        relative_path = m.group(1)
        asset = next(
            (a for a in self._spec.assets if a.relative_path == relative_path),
            None,
        )
        if asset is None:
            log.warning(
                "Intro references %r but asset not found in spec; skipping set_course_image",
                relative_path,
            )
            return

        filename = Path(asset.relative_path).name
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            ext = Path(filename).suffix.lower()
            mime = {"webp": "image/webp"}.get(
                ext.lstrip("."), "application/octet-stream"
            )

        imagedata = base64.b64encode(asset.absolute_path.read_bytes()).decode("ascii")
        log.info("Setting course image: %r (%s)", filename, mime)
        self._client.set_course_image(
            course_id=self._course_id,
            filename=filename,
            imagedata=imagedata,
            mimetype=mime,
        )

    def _create_sections(self) -> list[str]:
        """Rename each Moodle section (1-based) to match the corresponding part title.

        Section 0 is the Moodle general section and is left untouched.
        """
        titles: list[str] = []
        for i, part in enumerate(self._spec.parts):
            section_number = i + 1
            log.debug("Updating section %d: %r", section_number, part.title)
            self._client.update_section(
                course_id=self._course_id,
                section_number=section_number,
                name=part.title,
            )
            titles.append(part.title)
        return titles

    def _create_pages(
        self, asset_url_map: dict[str, str], link_map: dict[str, str]
    ) -> list[str]:
        """Create one Moodle Page activity per chapter, in section order."""
        titles: list[str] = []
        for i, part in enumerate(self._spec.parts):
            section_number = i + 1
            for chapter in part.chapters:
                content = _render_html(chapter.body, asset_url_map, link_map)
                log.debug(
                    "Creating page %r in section %d", chapter.title, section_number
                )
                self._client.create_page(
                    course_id=self._course_id,
                    section_number=section_number,
                    name=chapter.title,
                    content=content,
                )
                titles.append(chapter.title)
        return titles
