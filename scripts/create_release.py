
#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request

from pathlib import Path


REPO = os.environ["GITHUB_REPOSITORY"]
TAG = os.environ["RELEASE_TAG"].strip()
TITLE = os.environ["RELEASE_TITLE"].strip()
DESCRIPTION = os.environ.get("RELEASE_DESCRIPTION", "")
URLS = os.environ.get("ASSET_URLS", "")


def run(command):
    subprocess.run(command, check=True)


def parse_urls(value):
    """Virgül veya satır sonuyla ayrılmış URL'leri al."""

    urls = re.split(r"[,\r\n]+", value)

    result = []
    seen = set()

    for item in urls:
        url = item.strip()

        if not url:
            continue

        if url not in seen:
            result.append(url)
            seen.add(url)

    return result


def filename_from_url(url, index):
    parsed = urllib.parse.urlparse(url)

    name = Path(
        urllib.parse.unquote(parsed.path)
    ).name

    name = re.sub(
        r"[^A-Za-z0-9._()+ -]",
        "_",
        name
    ).strip(" .")

    if not name:
        name = f"download-{index}"

    return name[:180]


def release_exists():
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            TAG,
            "--repo",
            REPO
        ],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True

    error = (
        (result.stderr or "") +
        (result.stdout or "")
    ).lower()

    if (
        "not found" in error
        or "404" in error
        or "release not found" in error
    ):
        return False

    raise RuntimeError(
        "Release kontrol edilemedi:\n"
        + (result.stderr or result.stdout)
    )


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mesflit-Archive/1.0"
        }
    )

    print(f"İndiriliyor: {url}")

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        with open(destination, "wb") as output:

            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                output.write(chunk)

    if (
        not destination.is_file()
        or destination.stat().st_size == 0
    ):
        raise RuntimeError(
            f"Dosya boş veya indirilemedi: {url}"
        )


def main():

    if not REPO:
        raise ValueError(
            "GITHUB_REPOSITORY bulunamadı."
        )

    if not TAG or not TITLE:
        raise ValueError(
            "Tag ve başlık zorunludur."
        )

    urls = parse_urls(URLS)

    for url in urls:

        parsed = urllib.parse.urlparse(url)

        if (
            parsed.scheme not in ("https", "http")
            or not parsed.netloc
        ):
            raise ValueError(
                f"Geçersiz URL: {url}"
            )

    print(f"Repository: {REPO}")
    print(f"Release tag: {TAG}")
    print(f"Dosya sayısı: {len(urls)}")

    with tempfile.TemporaryDirectory() as temp:

        downloaded = []
        used_names = set()

        # Önce bütün dosyaları indir.
        # İndirme başarısız olursa Release değiştirilmez.

        for index, url in enumerate(urls, 1):

            name = filename_from_url(
                url,
                index
            )

            stem = Path(name).stem
            suffix = Path(name).suffix

            candidate = name
            counter = 2

            while candidate.lower() in used_names:

                candidate = (
                    f"{stem}-{counter}{suffix}"
                )

                counter += 1

            used_names.add(candidate.lower())

            destination = Path(temp) / candidate

            download_file(
                url,
                destination
            )

            downloaded.append(
                str(destination)
            )

        # Release kontrolü.

        if release_exists():

            print(
                "Mevcut Release güncelleniyor."
            )

            run([
                "gh",
                "release",
                "edit",
                TAG,
                "--repo",
                REPO,
                "--title",
                TITLE,
                "--notes",
                DESCRIPTION
            ])

        else:

            print(
                "Yeni Release oluşturuluyor."
            )

            run([
                "gh",
                "release",
                "create",
                TAG,
                "--repo",
                REPO,
                "--title",
                TITLE,
                "--notes",
                DESCRIPTION
            ])

        # Dosyaları Release'e yükle.
        # Aynı isimli asset varsa üzerine yaz.

        if downloaded:

            run([
                "gh",
                "release",
                "upload",
                TAG,
                *downloaded,
                "--repo",
                REPO,
                "--clobber"
            ])

    print(
        "Release başarıyla hazırlandı!"
    )


if __name__ == "__main__":
    main()
