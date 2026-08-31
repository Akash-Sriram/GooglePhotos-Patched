#!/usr/bin/env python3
"""
Download Google Photos APK from APKMirror.
Strategy:
  1. Fast path: curl_cffi with Chrome TLS impersonation (no overhead).
  2. Fallback: Playwright headless Chromium — executes the real Cloudflare JS
     challenge and carries the resulting cookies through all APKMirror steps.
"""
import sys
import os
import re
import argparse
import urllib.parse
import json

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("beautifulsoup4 not installed. Run: pip install beautifulsoup4 curl_cffi playwright")
    sys.exit(1)

DEFAULT_VARIANT_URL = (
    "https://www.apkmirror.com/apk/google-inc/photos/"
    "variant-%7B%22dpis_slug%22%3A%5B%22nodpi%22%5D%2C"
    "%22arches_slug%22%3A%5B%22arm64-v8a%22%2C%22armeabi-v7a%22%2C%22x86%22%2C%22x86_64%22%5D%7D/"
)

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cffi_get(url, headers, stream=False):
    resp = cffi_requests.get(url, headers=headers, impersonate=IMPERSONATE, stream=stream)
    resp.raise_for_status()
    return resp


def fetch_url(url, extra_headers=None):
    headers = HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)
    if HAS_CURL_CFFI:
        return _cffi_get(url, headers).content
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _stream_to_file(resp, output_path):
    with open(output_path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)


def download_file(url, output_path, extra_headers=None):
    headers = HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)

    if HAS_CURL_CFFI:
        resp = _cffi_get(url, headers, stream=True)
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
                print(f"Following redirect link: {direct_href}")
                resp = _cffi_get(direct_href, headers, stream=True)
        _stream_to_file(resp, output_path)
    else:
        import urllib.request
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(output_path, "wb") as fh:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                buf = resp.read(8192)
                if not buf:
                    break
                downloaded += len(buf)
                fh.write(buf)
                if total:
                    sys.stdout.write(f"\r{downloaded/total*100:.1f}%")
                    sys.stdout.flush()
            print()

# ---------------------------------------------------------------------------
# APKMirror HTML parsing helpers (shared by both paths)
# ---------------------------------------------------------------------------

def _find_detail_link(soup):
    """Return (detail_link, version_str) or (None, None)."""
    containers = soup.find_all("div", class_=re.compile(r"list-widget|widget-area|table-row"))
    candidates = containers if containers else [soup]
    for root in candidates:
        for a in root.find_all("a", href=True):
            href = a["href"]
            if "/apk/google-inc/photos/google-photos-" in href and (
                href.endswith("-download/") or "android-apk-download" in href
            ):
                link = urllib.parse.urljoin("https://www.apkmirror.com", href)
                m = re.search(r"google-photos-([0-9\-]+)", href)
                ver = m.group(1).replace("-", ".").rstrip(".") if m else None
                return link, ver
    return None, None


def _find_download_page_link(detail_soup):
    btn = detail_soup.find("a", class_=re.compile(r"downloadButton|accent_bg"))
    if btn and btn.get("href"):
        return urllib.parse.urljoin("https://www.apkmirror.com", btn["href"])
    for a in detail_soup.find_all("a", href=True):
        if "download.php" in a["href"] or "android-apk-download/" in a["href"]:
            link = urllib.parse.urljoin("https://www.apkmirror.com", a["href"])
            if "download.php" in a["href"]:
                return link
    return None


def _find_final_link(dl_soup, dl_html):
    for a in dl_soup.find_all("a", href=True):
        if (
            "key=" in a["href"]
            or "/wp-content/themes/APKMirror/" in a["href"]
            or "download.php" in a["href"]
        ):
            return urllib.parse.urljoin("https://www.apkmirror.com", a["href"])
    m = re.search(r'href="(/apk/google-inc/photos/[^"]+key=[^"]+)"', dl_html)
    if m:
        return urllib.parse.urljoin("https://www.apkmirror.com", m.group(1))
    return None

# ---------------------------------------------------------------------------
# Path 1: direct HTTP (fast, may fail with 403 on CI datacenter IPs)
# ---------------------------------------------------------------------------

def get_apkmirror_apk(variant_url, output_path, check_version_only=False):
    print(f"[direct] Fetching: {variant_url}")
    if HAS_CURL_CFFI:
        session = cffi_requests.Session(impersonate="chrome131")
        resp = session.get(variant_url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"HTTP Error {resp.status_code}: {resp.reason}")
        soup = BeautifulSoup(resp.text, "html.parser")
        detail_link, version_str = _find_detail_link(soup)
        if check_version_only:
            if not version_str:
                raise Exception("Could not determine version from APKMirror variant page.")
            print(f"LATEST_VERSION={version_str}")
            return version_str
        if not detail_link:
            raise Exception("Could not find download link on APKMirror variant page.")

        print(f"[direct] Detail page: {detail_link}")
        resp2 = session.get(detail_link, headers=HEADERS, timeout=30)
        if resp2.status_code != 200:
            raise Exception(f"HTTP Error {resp2.status_code}: {resp2.reason}")
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        dl_page = _find_download_page_link(soup2)
        if not dl_page:
            raise Exception("Could not find APK download button page.")

        print(f"[direct] Download page: {dl_page}")
        resp3 = session.get(dl_page, headers=HEADERS, timeout=30)
        if resp3.status_code != 200:
            raise Exception(f"HTTP Error {resp3.status_code}: {resp3.reason}")
        soup3 = BeautifulSoup(resp3.text, "html.parser")
        final_link = _find_final_link(soup3, resp3.text)
        if not final_link:
            raise Exception("Could not extract final download URL from APKMirror.")

        print(f"[direct] Downloading APK: {final_link}")
        dl_headers = {**HEADERS, "Referer": dl_page}
        dl_resp = session.get(final_link, headers=dl_headers, timeout=120, stream=True)
        if dl_resp.status_code != 200:
            raise Exception(f"Download HTTP Error {dl_resp.status_code}")
        _stream_to_file(dl_resp, output_path)
        return version_str
    else:
        html = fetch_url(variant_url).decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        detail_link, version_str = _find_detail_link(soup)
        if check_version_only:
            if not version_str:
                raise Exception("Could not determine version from APKMirror variant page.")
            print(f"LATEST_VERSION={version_str}")
            return version_str
        if not detail_link:
            raise Exception("Could not find download link on APKMirror variant page.")

        print(f"[direct] Detail page: {detail_link}")
        detail_html = fetch_url(detail_link).decode("utf-8")
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        dl_page = _find_download_page_link(detail_soup)
        if not dl_page:
            raise Exception("Could not find APK download button page.")

        print(f"[direct] Download page: {dl_page}")
        dl_html_raw = fetch_url(dl_page).decode("utf-8")
        dl_soup = BeautifulSoup(dl_html_raw, "html.parser")
        final_link = _find_final_link(dl_soup, dl_html_raw)
        if not final_link:
            raise Exception("Could not extract final download URL from APKMirror.")

        print(f"[direct] Downloading APK: {final_link}")
        download_file(final_link, output_path, extra_headers={"Referer": dl_page})
        return version_str


# ---------------------------------------------------------------------------
# Path 2: Playwright (headless Chromium — solves Cloudflare JS challenge)
# ---------------------------------------------------------------------------

def _pw_wait_for_cf(page, timeout=30000):
    """Wait until Cloudflare's 'Just a moment' interstitial clears."""
    try:
        page.wait_for_function(
            "() => !document.title.includes('Just a moment') && document.readyState === 'complete'",
            timeout=timeout,
        )
    except Exception:
        pass
    page.wait_for_timeout(2000)


def get_apkmirror_apk_playwright(variant_url, output_path, check_version_only=False):
    from playwright.sync_api import sync_playwright

    print("[playwright] Launching headless Chromium to bypass Cloudflare...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            accept_downloads=True,
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

        # Step 1: variant listing page
        print(f"[playwright] → {variant_url}")
        page.goto(variant_url, wait_until="domcontentloaded", timeout=60000)
        _pw_wait_for_cf(page)

        soup = BeautifulSoup(page.content(), "html.parser")
        detail_link, version_str = _find_detail_link(soup)

        if check_version_only:
            browser.close()
            if not version_str:
                raise Exception("[playwright] Could not determine version.")
            print(f"LATEST_VERSION={version_str}")
            return version_str

        if not detail_link:
            browser.close()
            raise Exception("[playwright] Could not find download link on APKMirror variant page.")

        # Step 2: APK detail page
        print(f"[playwright] → {detail_link}")
        page.goto(detail_link, wait_until="domcontentloaded", timeout=60000)
        _pw_wait_for_cf(page)

        detail_soup = BeautifulSoup(page.content(), "html.parser")
        dl_page = _find_download_page_link(detail_soup)
        if not dl_page:
            browser.close()
            raise Exception("[playwright] Could not find APK download button page.")

        # Step 3: download-button confirmation page
        print(f"[playwright] → {dl_page}")
        page.goto(dl_page, wait_until="domcontentloaded", timeout=60000)
        _pw_wait_for_cf(page)

        dl_html_raw = page.content()
        dl_soup = BeautifulSoup(dl_html_raw, "html.parser")
        final_link = _find_final_link(dl_soup, dl_html_raw)

        if not final_link:
            browser.close()
            raise Exception("[playwright] Could not extract final download URL from APKMirror.")

        # Step 4: download inside the live browser session by clicking download tag
        print(f"[playwright] Triggering APK download via browser session: {final_link}")
        with page.expect_download(timeout=300_000) as dl_info:
            a_tag = page.query_selector("a[href*='download.php']")
            if a_tag:
                a_tag.click()
            else:
                page.evaluate(f"window.location.href = {json.dumps(final_link)}")
        
        download = dl_info.value
        print(f"[playwright] Saving APK ({download.suggested_filename}) to: {output_path}")
        download.save_as(output_path)
        browser.close()

    return version_str



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Download Google Photos APK from APKMirror")
    parser.add_argument("--direct-url", type=str, help="Skip scraping; download this URL directly")
    parser.add_argument("--variant-url", type=str, default=DEFAULT_VARIANT_URL)
    parser.add_argument("--output", type=str, default="google-photos.apk")
    parser.add_argument("--check-version", action="store_true")
    args = parser.parse_args()

    # ---- direct URL shortcut ----
    if args.direct_url:
        print(f"Downloading direct URL: {args.direct_url}")
        download_file(args.direct_url, args.output)
        version_str = "unknown"
    else:
        version_str = "unknown"
        # Try fast path first, fall back to Playwright
        try:
            if args.check_version:
                get_apkmirror_apk(args.variant_url, None, check_version_only=True)
                return
            version_str = get_apkmirror_apk(args.variant_url, args.output)
        except Exception as e:
            print(f"Direct scrape failed ({e}); retrying with Playwright…")
            try:
                if args.check_version:
                    get_apkmirror_apk_playwright(args.variant_url, None, check_version_only=True)
                    return
                version_str = get_apkmirror_apk_playwright(args.variant_url, args.output)
            except Exception as e2:
                print(f"Playwright scrape also failed: {e2}")
                print("Pass --direct-url or trigger the workflow with a direct APK link.")
                sys.exit(1)

    # ---- validate download ----
    if os.path.exists(args.output) and os.path.getsize(args.output) > 1_000_000:
        print(
            f"Successfully downloaded {args.output} "
            f"({os.path.getsize(args.output):,} bytes)"
        )
        if "GITHUB_OUTPUT" in os.environ and version_str:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"apk_version={version_str}\n")
    else:
        print("Downloaded file is missing or too small!")
        sys.exit(1)


if __name__ == "__main__":
    main()
