#!/usr/bin/env python3
import sys
import os
import re
import argparse
import urllib.parse

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    import urllib.request
    HAS_CURL_CFFI = False

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("beautifulsoup4 not installed. Run: pip install beautifulsoup4 curl_cffi")
    sys.exit(1)

DEFAULT_VARIANT_URL = (
    "https://www.apkmirror.com/apk/google-inc/photos/"
    "variant-%7B%22dpis_slug%22%3A%5B%22nodpi%22%5D%2C"
    "%22arches_slug%22%3A%5B%22arm64-v8a%22%2C%22armeabi-v7a%22%2C%22x86%22%2C%22x86_64%22%5D%7D/"
)

# Impersonate a real Chrome browser to pass Cloudflare TLS fingerprint checks
IMPERSONATE = "chrome131"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
}


def fetch_url(url, extra_headers=None):
    headers = HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)

    if HAS_CURL_CFFI:
        resp = cffi_requests.get(url, headers=headers, impersonate=IMPERSONATE)
        resp.raise_for_status()
        return resp.content
    else:
        import urllib.request
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return resp.read()


def download_file(url, output_path, extra_headers=None):
    headers = HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)

    if HAS_CURL_CFFI:
        resp = cffi_requests.get(url, headers=headers, impersonate=IMPERSONATE, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type:
            # We landed on an intermediate HTML download page — find the real link
            soup = BeautifulSoup(resp.text, "html.parser")
            link = soup.find("a", id="download-link")
            if not link:
                for a in soup.find_all("a", href=True):
                    if "key=" in a["href"] or "download.php" in a["href"]:
                        link = a
                        break
            if link and link.get("href"):
                direct_href = urllib.parse.urljoin(url, link["href"])
                print(f"Following direct download link: {direct_href}")
                resp = cffi_requests.get(
                    direct_href, headers=headers, impersonate=IMPERSONATE, stream=True
                )
                resp.raise_for_status()
        with open(output_path, "wb") as out_file:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    out_file.write(chunk)
    else:
        import urllib.request
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(output_path, "wb") as out_file:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 8192
            while True:
                buffer = resp.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                if total > 0:
                    percent = downloaded / total * 100
                    sys.stdout.write(f"\rDownloading: {percent:.1f}% ({downloaded}/{total} bytes)")
                    sys.stdout.flush()
            print()


def get_apkmirror_apk(variant_url, output_path, check_version_only=False):
    print(f"Scraping variant list from: {variant_url}")
    html = fetch_url(variant_url).decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    detail_link = None
    version_str = None

    # Try scoped containers first to avoid sidebar/trending noise
    list_containers = soup.find_all("div", class_=re.compile(r"list-widget|widget-area|table-row"))
    for container in list_containers:
        for a in container.find_all("a", href=True):
            href = a["href"]
            if "/apk/google-inc/photos/google-photos-" in href and (
                href.endswith("-download/") or "android-apk-download" in href
            ):
                detail_link = urllib.parse.urljoin("https://www.apkmirror.com", href)
                match = re.search(r"google-photos-([0-9\-]+)", href)
                if match:
                    version_str = match.group(1).replace("-", ".").rstrip(".")
                break
        if detail_link:
            break

    # Fallback: scan all links on the page
    if not detail_link:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/apk/google-inc/photos/google-photos-" in href and (
                href.endswith("-download/") or "android-apk-download" in href
            ):
                detail_link = urllib.parse.urljoin("https://www.apkmirror.com", href)
                match = re.search(r"google-photos-([0-9\-]+)", href)
                if match:
                    version_str = match.group(1).replace("-", ".").rstrip(".")
                break

    if check_version_only:
        if not version_str:
            raise Exception("Could not determine latest version from APKMirror variant page.")
        print(f"LATEST_VERSION={version_str}")
        return version_str

    if not detail_link:
        raise Exception("Could not find download link on APKMirror variant page.")

    print(f"Found APK detail page: {detail_link}")
    detail_html = fetch_url(detail_link).decode("utf-8")
    detail_soup = BeautifulSoup(detail_html, "html.parser")

    download_page_link = None
    # Try official download button first
    btn = detail_soup.find("a", class_=re.compile(r"downloadButton|accent_bg"))
    if btn and btn.get("href"):
        download_page_link = urllib.parse.urljoin("https://www.apkmirror.com", btn["href"])

    if not download_page_link:
        for a in detail_soup.find_all("a", href=True):
            if "download.php" in a["href"] or "android-apk-download/" in a["href"]:
                download_page_link = urllib.parse.urljoin(
                    "https://www.apkmirror.com", a["href"]
                )
                if "download.php" in a["href"]:
                    break

    if not download_page_link:
        raise Exception("Could not find APK download button page.")

    print(f"Accessing download page: {download_page_link}")
    dl_html = fetch_url(download_page_link).decode("utf-8")
    dl_soup = BeautifulSoup(dl_html, "html.parser")

    final_link = None
    for a in dl_soup.find_all("a", href=True):
        if (
            "key=" in a["href"]
            or "/wp-content/themes/APKMirror/" in a["href"]
            or "download.php" in a["href"]
        ):
            final_link = urllib.parse.urljoin("https://www.apkmirror.com", a["href"])
            break

    if not final_link:
        match = re.search(r'href="(/apk/google-inc/photos/[^"]+key=[^"]+)"', dl_html)
        if match:
            final_link = urllib.parse.urljoin("https://www.apkmirror.com", match.group(1))

    if not final_link:
        raise Exception("Could not extract final download URL from APKMirror.")

    print(f"Downloading final APK from: {final_link}")
    download_file(final_link, output_path, extra_headers={"Referer": download_page_link})
    return version_str


def main():
    parser = argparse.ArgumentParser(description="Download Google Photos APK")
    parser.add_argument("--direct-url", type=str, help="Direct URL to APK file")
    parser.add_argument(
        "--variant-url",
        type=str,
        default=DEFAULT_VARIANT_URL,
        help="APKMirror variant page URL",
    )
    parser.add_argument(
        "--output", type=str, default="google-photos.apk", help="Output path for downloaded APK"
    )
    parser.add_argument(
        "--check-version", action="store_true", help="Only check and output latest version"
    )
    args = parser.parse_args()

    if args.check_version:
        get_apkmirror_apk(args.variant_url, None, check_version_only=True)
        return

    if args.direct_url:
        print(f"Downloading direct URL: {args.direct_url}")
        download_file(args.direct_url, args.output)
        version_str = "unknown"
    else:
        version_str = "unknown"
        try:
            version_str = get_apkmirror_apk(args.variant_url, args.output)
        except Exception as e:
            print(f"Error scraping APKMirror: {e}")
            print(
                "Notice: If APKMirror blocked the runner, pass --direct-url "
                "or run the workflow with a direct input link."
            )
            sys.exit(1)

    if os.path.exists(args.output) and os.path.getsize(args.output) > 1_000_000:
        print(
            f"Successfully downloaded APK to {args.output} "
            f"(Size: {os.path.getsize(args.output)} bytes)"
        )
        if "GITHUB_OUTPUT" in os.environ and version_str:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"apk_version={version_str}\n")
    else:
        print("Downloaded file is missing or too small!")
        sys.exit(1)


if __name__ == "__main__":
    main()
