
#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile

from pathlib import Path


REPO = os.environ["GITHUB_REPOSITORY"]
TAG = os.environ["RELEASE_TAG"].strip()
TITLE = os.environ["RELEASE_TITLE"].strip()
DESCRIPTION = os.environ.get("RELEASE_DESCRIPTION", "")
URLS = os.environ.get("ASSET_URLS", "")

# GitHub Release dosya boyutu sınırı
MAX_ASSET_SIZE = 2 * 1024**3

# Her parçanın boyutu: 1900 MiB
PART_SIZE = 1900 * 1024**2

BUFFER_SIZE = 16 * 1024**2


def run(command):
    subprocess.run(command, check=True)


def parse_urls(value):
    """Virgül veya satır sonuyla ayrılmış URL'leri al."""

    urls = re.split(r"[,\r\n]+", value)

    result = []
    seen = set()

    for item in urls:
        url = item.strip()

        if url and url not in seen:
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


def unique_name(name, used_names):
    stem = Path(name).stem
    suffix = Path(name).suffix

    candidate = name
    counter = 2

    while candidate.lower() in used_names:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1

    used_names.add(candidate.lower())

    return candidate


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
            "User-Agent": "Mesflit-Archive/2.0"
        }
    )

    print(f"\nİndiriliyor: {url}")

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        with open(destination, "wb") as output:

            while True:
                chunk = response.read(BUFFER_SIZE)

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

    size = destination.stat().st_size

    print(
        f"İndirme tamamlandı: "
        f"{size / 1024**3:.2f} GiB"
    )


def create_zip(source, destination):
    """Dosyayı ZIP64 destekli ZIP arşivine dönüştür."""

    print(f"\nZIP oluşturuluyor: {source.name}")

    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True
    ) as archive:

        archive.write(
            source,
            arcname=source.name
        )

    size = destination.stat().st_size

    print(
        f"ZIP tamamlandı: "
        f"{size / 1024**3:.2f} GiB"
    )


def split_archive(archive):
    """ZIP arşivini 1900 MiB parçalarına böl."""

    print(f"\nParçalanıyor: {archive.name}")

    parts = []

    with open(archive, "rb") as source:

        index = 1

        while True:

            part_name = (
                f"{archive.name}.{index:06d}"
            )

            part_path = archive.parent / part_name

            written = 0

            with open(part_path, "wb") as output:

                while written < PART_SIZE:

                    chunk = source.read(
                        min(
                            BUFFER_SIZE,
                            PART_SIZE - written
                        )
                    )

                    if not chunk:
                        break

                    output.write(chunk)
                    written += len(chunk)

            if written == 0:
                part_path.unlink(missing_ok=True)
                break

            parts.append(part_path)

            print(
                f"Parça {index}: "
                f"{written / 1024**2:.2f} MiB"
            )

            index += 1

    archive.unlink()

    print(
        f"Parçalama tamamlandı: {len(parts)} parça"
    )

    return parts


def create_join_scripts(directory, used_names):
    """Linux ve Windows için birleştirme araçları oluştur."""

    shell_name = unique_name(
        "MESFLIT-JOIN-PARTS.sh",
        used_names
    )

    powershell_name = unique_name(
        "MESFLIT-JOIN-PARTS.ps1",
        used_names
    )

    shell_script = directory / shell_name

    shell_script.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]]; then
    echo "Kullanım: $0 arsiv.zip"
    exit 1
fi

archive="$1"

shopt -s nullglob
export LC_ALL=C

parts=( "${archive}".[0-9][0-9][0-9][0-9][0-9][0-9] )

if [[ ${#parts[@]} -eq 0 ]]; then
    echo "Arşiv parçaları bulunamadı."
    exit 1
fi

cat "${parts[@]}" > "${archive}.tmp"
mv "${archive}.tmp" "$archive"

echo "Arşiv başarıyla birleştirildi: $archive"
""",
        encoding="utf-8"
    )

    powershell_script = directory / powershell_name

    powershell_script.write_text(
        r"""param(
    [Parameter(Mandatory=$true)]
    [string]$Archive
)

$ErrorActionPreference = "Stop"

$full = [IO.Path]::GetFullPath($Archive)
$directory = Split-Path -Parent $full
$leaf = Split-Path -Leaf $full

if ([string]::IsNullOrEmpty($directory)) {
    $directory = (Get-Location).Path
}

$pattern = '^' + [regex]::Escape($leaf) + '\.\d{6}$'

$parts = @(
    Get-ChildItem -LiteralPath $directory -File |
    Where-Object { $_.Name -match $pattern } |
    Sort-Object Name
)

if ($parts.Count -eq 0) {
    throw "Arşiv parçaları bulunamadı."
}

$tmp = "$full.tmp"

$out = [IO.File]::Open(
    $tmp,
    [IO.FileMode]::Create,
    [IO.FileAccess]::Write,
    [IO.FileShare]::None
)

try {
    foreach ($part in $parts) {
        Write-Host "Birleştiriliyor: $($part.Name)"

        $input = [IO.File]::OpenRead($part.FullName)

        try {
            $input.CopyTo($out)
        }
        finally {
            $input.Dispose()
        }
    }
}
finally {
    $out.Dispose()
}

Move-Item -LiteralPath $tmp -Destination $full -Force

Write-Host "Arşiv başarıyla birleştirildi: $full"
""",
        encoding="utf-8"
    )

    return [
        shell_script,
        powershell_script
    ]


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

        directory = Path(temp)

        downloaded = []
        used_names = set()

        # 1. Bütün dosyaları indir.

        for index, url in enumerate(urls, 1):

            name = unique_name(
                filename_from_url(url, index),
                used_names
            )

            destination = directory / name

            download_file(
                url,
                destination
            )

            downloaded.append(destination)

        # 2. Dosya boyutlarını kontrol et.
        # Büyük dosyaları ZIP64 ile sıkıştır.

        upload_files = []
        has_split_archives = False

        for source in downloaded:

            size = source.stat().st_size

            if size < MAX_ASSET_SIZE:

                print(
                    f"\nNormal dosya: {source.name}"
                )

                upload_files.append(source)
                continue

            print(
                f"\nBüyük dosya algılandı: {source.name}"
            )

            archive_name = unique_name(
                source.name + ".zip",
                used_names
            )

            archive_path = directory / archive_name

            create_zip(
                source,
                archive_path
            )

            # ZIP oluşturulduktan sonra orijinali sil.
            source.unlink()

            archive_size = archive_path.stat().st_size

            if archive_size < MAX_ASSET_SIZE:

                print(
                    "ZIP 2 GiB sınırının altında. "
                    "Tek dosya olarak yüklenecek."
                )

                upload_files.append(archive_path)

            else:

                parts = split_archive(
                    archive_path
                )

                upload_files.extend(parts)
                has_split_archives = True

        # 3. Birleştirme araçlarını oluştur.

        if has_split_archives:

            print("\nBirleştirme araçları oluşturuluyor.")

            helpers = create_join_scripts(
                directory,
                used_names
            )

            upload_files.extend(helpers)

        # 4. Bütün işlemler tamamlandıktan sonra
        # Release oluştur veya güncelle.

        if release_exists():

            print(
                "\nMevcut Release güncelleniyor."
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
                "\nYeni Release oluşturuluyor."
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

        # 5. Bütün dosyaları yükle.

        if upload_files:

            print(
                f"\nToplam yüklenecek asset: "
                f"{len(upload_files)}"
            )

            run([
                "gh",
                "release",
                "upload",
                TAG,
                *[str(path) for path in upload_files],
                "--repo",
                REPO,
                "--clobber"
            ])

        print("\nRelease başarıyla hazırlandı!")


if __name__ == "__main__":
    main()
