
#!/usr/bin/env python3
"""Generate Mesflit Archive from GitHub Releases."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import bleach
import markdown


REPO = os.environ.get(
    "GITHUB_REPOSITORY",
    "mesflit/archive"
)

TOKEN = os.environ.get("GITHUB_TOKEN", "")

API_ROOT = f"https://api.github.com/repos/{REPO}"

SITE = Path("site")
RELEASES_DIR = SITE / "releases"


# --------------------------------------------------
# GITHUB API
# --------------------------------------------------

def api_get(url: str):

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Mesflit-Archive-Builder",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(
        url,
        headers=headers
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


def get_releases():

    releases = []
    page = 1

    while True:

        url = (
            f"{API_ROOT}/releases"
            f"?per_page=100&page={page}"
        )

        batch = api_get(url)

        if not batch:
            break

        releases.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return releases


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def safe_tag(tag: str) -> str:

    return urllib.parse.quote(
        tag,
        safe="-._~"
    )


def esc(value) -> str:

    return html.escape(
        str(value or ""),
        quote=True
    )


def human_size(size: int) -> str:

    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)

    for unit in units:

        if value < 1024 or unit == units[-1]:

            if unit == "B":
                return f"{int(value)} B"

            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} B"


def date_label(value: str) -> str:

    if not value:
        return "Tarih belirtilmemiş"

    try:

        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return dt.astimezone(
            timezone.utc
        ).strftime("%d %b %Y")

    except ValueError:

        return value


def icon_asset(release):

    for asset in release.get("assets", []):

        if (
            asset.get("name", "").lower()
            == "icon.png"
        ):
            return asset.get("browser_download_url")

    return None


def render_markdown(value: str) -> str:
    """Markdown metnini güvenli HTML'ye dönüştür."""

    rendered = markdown.markdown(
        value or "",
        extensions=[
            "fenced_code",
            "tables",
            "nl2br",
            "sane_lists",
        ]
    )

    allowed_tags = set(
        bleach.sanitizer.ALLOWED_TAGS
    ).union({
        "p", "h1", "h2", "h3", "h4",
        "pre", "code", "blockquote",
        "ul", "ol", "li",
        "hr", "br", "img",
        "table", "thead", "tbody",
        "tr", "th", "td",
        "del", "sup", "sub",
    })

    allowed_attributes = {
        "a": ["href", "title"],
        "img": ["src", "alt", "title", "width", "height"],
        "code": ["class"],
        "pre": ["class"],
        "th": ["align"],
        "td": ["align"],
    }

    return bleach.clean(
        rendered,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols={"http", "https", "mailto"},
        strip=True,
    )


class PlainTextParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def markdown_summary(value: str, limit: int = 150) -> str:

    rendered = render_markdown(value)

    parser = PlainTextParser()
    parser.feed(rendered)

    text = re.sub(
        r"\s+",
        " ",
        " ".join(parser.parts)
    ).strip()

    if len(text) > limit:
        return text[:limit].rstrip() + "…"

    return text


# --------------------------------------------------
# RELEASE PAGE
# --------------------------------------------------

def render_release_page(
    release,
    repo: str,
    base: str
) -> str:

    title = (
        release.get("name")
        or release.get("tag_name")
        or "Untitled release"
    )

    tag = (
        release.get("tag_name")
        or "untagged"
    )

    body = (
        release.get("body")
        or "Bu sürüm için açıklama eklenmemiş."
    )

    assets = release.get("assets", [])
    icon = icon_asset(release)

    if icon:

        icon_html = f"""
        <img
            class="release-icon"
            src="{esc(icon)}"
            alt=""
            onerror="this.style.display='none'"
        >
        """

    else:

        icon_html = """
        <div class="release-icon icon-placeholder">
            📦
        </div>
        """

    asset_rows = []

    for asset in assets:

        name = asset.get("name") or "Dosya"

        url = (
            asset.get("browser_download_url")
            or "#"
        )

        size = human_size(
            int(asset.get("size") or 0)
        )

        asset_rows.append(f"""
        <a
            class="asset"
            href="{esc(url)}"
            target="_blank"
            rel="noopener noreferrer"
        >
            <span class="asset-symbol">↓</span>

            <span class="asset-info">
                <strong>{esc(name)}</strong>
                <small>{esc(size)}</small>
            </span>

            <span class="asset-download">
                İndir
            </span>
        </a>
        """)

    if not asset_rows:

        asset_rows.append("""
        <p class="muted">
            Bu release içinde indirilebilir dosya bulunmuyor.
        </p>
        """)

    github_url = (
        f"https://github.com/{repo}/releases/tag/"
        f"{urllib.parse.quote(tag, safe='')}"
    )

    return f"""<!doctype html>
<html lang="tr">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <meta name="theme-color" content="#0b1020">

    <meta
        name="description"
        content="{esc(title)} — Mesflit Archive"
    >

    <title>{esc(title)} · Mesflit Archive</title>

    <link
        rel="stylesheet"
        href="{esc(base)}assets/style.css"
    >
</head>

<body>
    <div class="ambient"></div>

    <header class="topbar">
        <a class="brand" href="{esc(base)}">
            <span class="brand-mark">M</span>

            <span>
                Mesflit <b>Archive</b>
            </span>
        </a>

        <a class="back-link" href="{esc(base)}">
            ← Tüm arşivler
        </a>
    </header>

    <main class="container detail-container">

        <div class="breadcrumbs">
            <a href="{esc(base)}">Arşiv</a>
            <span>/</span>
            <span>{esc(tag)}</span>
        </div>

        <section class="detail-hero panel">
            {icon_html}

            <div class="detail-heading">
                <span class="eyebrow">
                    GITHUB RELEASE
                </span>

                <h1>{esc(title)}</h1>

                <div class="meta">
                    <span>{esc(tag)}</span>
                    <span>·</span>
                    <span>
                        {esc(date_label(release.get("published_at")))}
                    </span>
                </div>
            </div>
        </section>

        <section class="content-section">
            <div class="section-heading">
                <div>
                    <span class="eyebrow">ABOUT</span>
                    <h2>Açıklama</h2>
                </div>
            </div>

            <div class="panel description markdown-content">
                {render_markdown(body)}
            </div>
        </section>

        <section class="content-section">
            <div class="section-heading">
                <div>
                    <span class="eyebrow">DOWNLOADS</span>

                    <h2>
                        Dosyalar
                        <span class="count">{len(assets)}</span>
                    </h2>
                </div>
            </div>

            <div class="asset-list">
                {''.join(asset_rows)}
            </div>
        </section>

        <footer class="footer">
            Mesflit Archive ·

            <a
                href="{esc(github_url)}"
                target="_blank"
                rel="noopener noreferrer"
            >
                GitHub üzerinde görüntüle ↗
            </a>
        </footer>

    </main>
</body>
</html>"""


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

def render_home(releases, repo: str) -> str:

    cards = []

    for release in releases:

        title = (
            release.get("name")
            or release.get("tag_name")
            or "Untitled release"
        )

        tag = (
            release.get("tag_name")
            or "untagged"
        )

        slug = safe_tag(tag)
        icon = icon_asset(release)

        if icon:

            image = f"""
            <img
                src="{esc(icon)}"
                alt=""
                loading="lazy"
                onerror="this.outerHTML='&lt;span&gt;📦&lt;/span&gt;'"
            >
            """

        else:

            image = "<span>📦</span>"

        body = release.get("body") or ""

        summary = markdown_summary(body)

        if icon:
            pass

        cards.append(f"""
        <a
            class="archive-card"
            href="releases/{esc(slug)}/"
        >
            <div class="card-icon">
                {image}
            </div>

            <div class="card-content">

                <div class="card-topline">
                    <span class="tag">
                        {esc(tag)}
                    </span>

                    <span class="file-count">
                        {len(release.get("assets", []))} dosya
                    </span>
                </div>

                <h3>{esc(title)}</h3>

                <p>
                    {esc(summary or "Bu arşiv için açıklama bulunmuyor.")}
                </p>

                <div class="card-bottom">
                    <span>
                        {esc(date_label(release.get("published_at")))}
                    </span>

                    <span class="card-arrow">↗</span>
                </div>

            </div>
        </a>
        """)

    cards_html = "".join(cards)

    if not cards_html:

        cards_html = """
        <div class="empty-state">
            <div class="empty-icon">📦</div>

            <h3>Henüz arşiv yok</h3>

            <p>
                İlk GitHub Release yayınlandığında burada görünecek.
            </p>
        </div>
        """

    return f"""<!doctype html>
<html lang="tr">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <meta name="theme-color" content="#0b1020">

    <meta
        name="description"
        content="Mesflit Archive — Dosyalar, araçlar ve projeler için dijital arşiv."
    >

    <title>Mesflit Archive</title>

    <link
        rel="stylesheet"
        href="assets/style.css"
    >
</head>

<body>
    <div class="ambient"></div>

    <header class="topbar">
        <a class="brand" href="./">
            <span class="brand-mark">M</span>

            <span>
                Mesflit <b>Archive</b>
            </span>
        </a>

        <a
            class="github-link"
            href="https://github.com/{esc(repo)}/releases"
            target="_blank"
            rel="noopener noreferrer"
        >
            GitHub Releases ↗
        </a>
    </header>

    <main class="container">

        <section class="hero">
            <div class="hero-copy">
                <span class="eyebrow">
                    <span class="status-dot"></span>
                    DIGITAL COLLECTION
                </span>

                <h1>
                    Everything,<br>
                    <span>in one archive.</span>
                </h1>

                <p>
                    Projeler, araçlar ve dosyalar.
                    Düzenli, erişilebilir ve tek bir yerde.
                </p>
            </div>

            <div class="hero-orbit">
                <div class="orbit orbit-one"></div>
                <div class="orbit orbit-two"></div>
                <div class="orbit-core">M</div>
                <span class="orbit-star">✦</span>
            </div>
        </section>

        <section class="archive-section">
            <div class="section-heading">
                <div>
                    <span class="eyebrow">
                        THE COLLECTION
                    </span>

                    <h2>
                        Arşivler
                        <span class="count">{len(releases)}</span>
                    </h2>
                </div>
            </div>

            <label class="search-box">
                <span class="search-icon">⌕</span>

                <input
                    id="search"
                    type="search"
                    placeholder="Arşivlerde ara..."
                    autocomplete="off"
                >

                <kbd>/</kbd>
            </label>

            <div
                class="archive-grid"
                id="archive-grid"
            >
                {cards_html}
            </div>

            <p
                class="no-results"
                id="no-results"
                hidden
            >
                Aramanla eşleşen bir arşiv bulunamadı.
            </p>
        </section>

        <footer class="footer">
            © {datetime.now(timezone.utc).year}
            Mesflit · Archive
        </footer>

    </main>

    <script src="assets/app.js"></script>
</body>
</html>"""


# --------------------------------------------------
# CLEANUP
# --------------------------------------------------

def cleanup_deleted_releases(releases):

    expected_slugs = {
        safe_tag(
            release.get("tag_name")
            or f"release-{release.get('id')}"
        )
        for release in releases
    }

    for old_dir in RELEASES_DIR.iterdir():

        if old_dir.is_dir():

            if old_dir.name not in expected_slugs:

                print(
                    f"Removing deleted release: {old_dir}"
                )

                shutil.rmtree(old_dir)

        elif old_dir.is_file():

            print(
                f"Removing unexpected file: {old_dir}"
            )

            old_dir.unlink()


# --------------------------------------------------
# MAIN GENERATOR
# --------------------------------------------------

def main():

    SITE.mkdir(
        parents=True,
        exist_ok=True
    )

    RELEASES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    (SITE / "assets").mkdir(
        parents=True,
        exist_ok=True
    )

    releases = get_releases()

    releases.sort(
        key=lambda r: (
            r.get("published_at")
            or r.get("created_at")
            or ""
        ),
        reverse=True
    )

    # GitHub'da artık bulunmayan sayfaları temizle.
    cleanup_deleted_releases(releases)

    created = 0
    updated = 0

    for release in releases:

        tag = (
            release.get("tag_name")
            or f"release-{release.get('id')}"
        )

        slug = safe_tag(tag)

        page_dir = RELEASES_DIR / slug
        page_file = page_dir / "index.html"

        existed = page_file.exists()

        page_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        page_file.write_text(
            render_release_page(
                release,
                REPO,
                "../../"
            ),
            encoding="utf-8"
        )

        if existed:

            updated += 1
            print(f"Updated: {page_file}")

        else:

            created += 1
            print(f"Created: {page_file}")

    # Ana sayfayı her çalıştırmada yenile.

    home_page = SITE / "index.html"

    home_page.write_text(
        render_home(releases, REPO),
        encoding="utf-8"
    )

    print("-----------------------------------")
    print("Mesflit Archive generation complete!")
    print(f"New pages: {created}")
    print(f"Updated pages: {updated}")
    print(f"Total releases: {len(releases)}")
    print("-----------------------------------")


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print(
            f"Archive generation failed: {exc}",
            file=sys.stderr
        )

        raise
