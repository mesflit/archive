
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


def filename_from_url(url, index):
    name = Path(
        urllib.parse.unquote(
            urllib.parse.urlparse(url).path
        )
    ).name

    name = re.sub(r"[^A-Za-z0-9._()+ -]", "_", name)

    if not name:
        name = f"download-{index}"

    return name[:180]


def main():

    if not TAG or not TITLE:
        raise ValueError("Tag ve başlık zorunludur.")

    urls = [
        line.strip()
        for line in URLS.splitlines()
        if line.strip()
    ]

    for url in urls:
        parsed = urllib.parse.urlparse(url)

        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError(f"Geçersiz URL: {url}")

    with tempfile.TemporaryDirectory() as temp:

        downloaded = []
        used_names = set()

        for index, url in enumerate(urls, 1):

            name = filename_from_url(url, index)

            stem = Path(name).stem
            suffix = Path(name).suffix

            candidate = name
            counter = 2

            while candidate.lower() in used_names:
                candidate = f"{stem}-{counter}{suffix}"
                counter += 1

            used_names.add(candidate.lower())

            destination = Path(temp) / candidate

            print("İndiriliyor:", url)

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mesflit-Archive"
                }
            )

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

            if destination.stat().st_size == 0:
                raise ValueError(f"Dosya boş: {url}")

            downloaded.append(str(destination))

        # Release mevcut mu?
        exists = subprocess.run(
            [
                "gh", "release", "view",
                TAG,
                "--repo", REPO
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ).returncode == 0

        if exists:

            print("Mevcut Release güncelleniyor.")

            run([
                "gh", "release", "edit",
                TAG,
                "--repo", REPO,
                "--title", TITLE,
                "--notes", DESCRIPTION
            ])

        else:

            print("Yeni Release oluşturuluyor.")

            run([
                "gh", "release", "create",
                TAG,
                "--repo", REPO,
                "--title", TITLE,
                "--notes", DESCRIPTION
            ])

        # Dosyaları yükle
        if downloaded:

            run([
                "gh", "release", "upload",
                TAG,
                *downloaded,
                "--repo", REPO
            ])

    print("Release başarıyla hazırlandı!")


if __name__ == "__main__":
    main()
  
