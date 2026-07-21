#!/usr/bin/env python3
import sys
import os
import re
import argparse
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

DEFAULT_VARIANT_URL = "https://www.apkmirror.com/apk/google-inc/photos/variant-%7B%22dpis_slug%22%3A%5B%22nodpi%22%5D%2C%22arches_slug%22%3A%5B%22arm64-v8a%22%5D%7D/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}

def get_scraper():
    try:
        import cloudscraper
        return cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    except ImportError:
        return None

def fetch_url(url, extra_headers=None):
    headers = HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)
    scraper = get_scraper()
    if scraper:
        resp = scraper.get(url, headers=headers)
        return resp.content
    else:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return resp.read()

def download_file(url, output_path, extra_headers=None):
    headers = HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)
    scraper = get_scraper()
    if scraper:
        resp = scraper.get(url, headers=headers, stream=True)
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type:
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
                resp = scraper.get(direct_href, headers=headers, stream=True)
        with open(output_path, "wb") as out_file:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    out_file.write(chunk)
    else:
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
    version_str = "unknown"
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/apk/google-inc/photos/google-photos-" in href and (href.endswith("-download/") or "android-apk-download" in href):
            detail_link = urllib.parse.urljoin("https://www.apkmirror.com", href)
            match = re.search(r'google-photos-([0-9\-]+)', href)
            if match:
                version_str = match.group(1).replace('-', '.')
            break

    if not detail_link:
        rows = soup.find_all("div", class_="table-row")
        for row in rows:
            a = row.find("a", class_="accent_color", href=True)
            if a and "/apk/google-inc/photos/" in a["href"]:
                detail_link = urllib.parse.urljoin("https://www.apkmirror.com", a["href"])
                match = re.search(r'google-photos-([0-9\-]+)', a["href"])
                if match:
                    version_str = match.group(1).replace('-', '.')
                break

    if check_version_only:
        print(f"LATEST_VERSION={version_str}")
        return version_str

    if not detail_link:
        raise Exception("Could not find download link on APKMirror variant page.")

    print(f"Found APK detail page: {detail_link}")
    detail_html = fetch_url(detail_link).decode("utf-8")
    detail_soup = BeautifulSoup(detail_html, "html.parser")

    download_page_link = None
    for a in detail_soup.find_all("a", href=True):
        if "download.php" in a["href"] or "android-apk-download/" in a["href"]:
            download_page_link = urllib.parse.urljoin("https://www.apkmirror.com", a["href"])
            if "download.php" in a["href"]:
                break

    if not download_page_link:
        btn = detail_soup.find("a", class_=re.compile(r"downloadButton"))
        if btn and btn.get("href"):
            download_page_link = urllib.parse.urljoin("https://www.apkmirror.com", btn["href"])

    if not download_page_link:
        raise Exception("Could not find APK download button page.")

    print(f"Accessing download page: {download_page_link}")
    dl_html = fetch_url(download_page_link).decode("utf-8")
    dl_soup = BeautifulSoup(dl_html, "html.parser")

    final_link = None
    for a in dl_soup.find_all("a", href=True):
        if "key=" in a["href"] or "/wp-content/themes/APKMirror/" in a["href"] or "download.php" in a["href"]:
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
    parser.add_argument("--variant-url", type=str, default=DEFAULT_VARIANT_URL, help="APKMirror variant page URL")
    parser.add_argument("--output", type=str, default="google-photos.apk", help="Output path for downloaded APK")
    parser.add_argument("--check-version", action="store_true", help="Only check and output latest version")
    args = parser.parse_args()

    if args.check_version:
        get_apkmirror_apk(args.variant_url, None, check_version_only=True)
        return

    if args.direct_url:
        print(f"Downloading direct URL: {args.direct_url}")
        download_file(args.direct_url, args.output)
    else:
        version_str = "unknown"
        try:
            version_str = get_apkmirror_apk(args.variant_url, args.output)
        except Exception as e:
            print(f"Error scraping APKMirror: {e}")
            print("Notice: If APKMirror blocked the runner, pass --direct-url or run workflow with direct input link.")
            sys.exit(1)

    if os.path.exists(args.output) and os.path.getsize(args.output) > 1000000:
        print(f"Successfully downloaded APK to {args.output} (Size: {os.path.getsize(args.output)} bytes)")
        if "GITHUB_OUTPUT" in os.environ and version_str:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"apk_version={version_str}\n")
    else:
        print("Downloaded file is missing or too small!")
        sys.exit(1)

if __name__ == "__main__":
    main()
