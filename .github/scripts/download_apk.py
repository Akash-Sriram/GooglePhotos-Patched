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
import time
import subprocess
import shutil
from pathlib import Path

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
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

def _parse_version_tuple(ver_str):
    if not ver_str:
        return (0,)
    parts = re.findall(r"\d+", ver_str)
    return tuple(int(p) for p in parts) if parts else (0,)


def _find_detail_link(soup):
    """Return (detail_link, version_str) for the highest semantic version on the page."""
    containers = soup.find_all("div", class_=re.compile(r"list-widget|widget-area|table-row"))
    candidates = containers if containers else [soup]
    found = []
    seen_links = set()
    for root in candidates:
        for a in root.find_all("a", href=True):
            href = a["href"]
            if "/apk/google-inc/photos/google-photos-" in href and (
                href.endswith("-download/") or "android-apk-download" in href
            ):
                link = urllib.parse.urljoin("https://www.apkmirror.com", href).split("#")[0]
                if link in seen_links:
                    continue
                seen_links.add(link)
                m = re.search(r"google-photos-([0-9\-]+)", href)
                ver = m.group(1).replace("-", ".").rstrip(".") if m else None
                if ver:
                    found.append((link, ver, _parse_version_tuple(ver)))

    if not found:
        return None, None

    # Sort by semantic version descending so the highest version (e.g. 7.90.0 > 7.89.0) is always chosen
    found.sort(key=lambda x: x[2], reverse=True)
    best_link, best_ver, _ = found[0]
    print(f"[APKMirror] Found {len(found)} releases on page. Picked highest semantic version: {best_ver}")
    return best_link, best_ver


def _find_fallback_detail_link(session=None):
    """Scrapes the main /apk/google-inc/photos/ page and looks inside the latest release
    variants table for a Universal nodpi APK (non-bundle)."""
    main_url = "https://www.apkmirror.com/apk/google-inc/photos/"
    try:
        if session:
            resp = session.get(main_url, headers=HEADERS, timeout=30)
            html = resp.text
        else:
            html = fetch_url(main_url).decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/apk/google-inc/photos/google-photos-" in href and href.endswith("-release/"):
                rel_url = urllib.parse.urljoin("https://www.apkmirror.com", href)
                print(f"[fallback] Checking main release page: {rel_url}")
                if session:
                    rel_resp = session.get(rel_url, headers=HEADERS, timeout=30)
                    rel_html = rel_resp.text
                else:
                    rel_html = fetch_url(rel_url).decode("utf-8")
                rel_soup = BeautifulSoup(rel_html, "html.parser")
                for row in rel_soup.find_all("div", class_="table-row"):
                    text = " ".join(row.stripped_strings).lower()
                    if "variant" in text and "arch" in text:
                        continue
                    if "apk" in text and "bundle" not in text and "nodpi" in text:
                        if "universal" in text or ("arm64-v8a" in text and "x86" in text):
                            for link in row.find_all("a", href=True):
                                if "download" in link["href"]:
                                    dl_link = urllib.parse.urljoin("https://www.apkmirror.com", link["href"]).split("#")[0]
                                    m = re.search(r"google-photos-([0-9\-]+)", dl_link)
                                    ver = m.group(1).replace("-", ".").rstrip(".") if m else None
                                    print(f"[fallback] Found Universal variant link: {dl_link} (ver: {ver})")
                                    return dl_link, ver
    except Exception as e:
        print(f"[fallback] Error querying main release page: {e}")
    return None, None



def _find_download_page_link(detail_soup, detail_url=None):
    btn = detail_soup.find("a", class_=re.compile(r"downloadButton|accent_bg|download-btn", re.I))
    if btn and btn.get("href"):
        return urllib.parse.urljoin("https://www.apkmirror.com", btn["href"]).split("#")[0]
    for a in detail_soup.find_all("a", href=True):
        text = a.get_text().strip().lower()
        title = a.get("title", "").strip().lower()
        href = a["href"].strip()
        if "download apk" in text or "download apk" in title:
            return urllib.parse.urljoin("https://www.apkmirror.com", href).split("#")[0]
        if href.endswith("/download/") or "/download/?" in href:
            return urllib.parse.urljoin("https://www.apkmirror.com", href).split("#")[0]
        if "download.php" in href:
            return urllib.parse.urljoin("https://www.apkmirror.com", href).split("#")[0]
    if detail_url and ("android-apk-download" in detail_url or detail_url.endswith("-download/")):
        constructed = f"{detail_url.rstrip('/')}/download/"
        print(f"[download-link] Using fallback constructed download page: {constructed}")
        return constructed
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
        if not detail_link:
            print("[direct] No release link on variant page; trying dynamic catalog fallback...")
            detail_link, version_str = _find_fallback_detail_link(session=session)
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
        dl_page = _find_download_page_link(soup2, detail_link)
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
        if not detail_link:
            print("[direct] No release link on variant page; trying dynamic catalog fallback...")
            detail_link, version_str = _find_fallback_detail_link()
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
        dl_page = _find_download_page_link(detail_soup, detail_link)
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

def _ensure_playwright():
    """Install playwright, playwright-stealth, and chromium browser binaries on-demand if missing."""
    try:
        import playwright
        import playwright_stealth
        return True
    except ImportError:
        print("[setup] Installing Playwright, playwright-stealth, and Chromium on demand...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "playwright-stealth"])
        subprocess.check_call(["playwright", "install", "chromium", "--with-deps"])
        return True


def _pw_wait_for_cf(page, timeout=45000):
    """Wait until Cloudflare challenge clears, detecting and clicking Turnstile checkbox if present."""
    start_time = time.time()
    last_click_time = 0.0

    while time.time() - start_time < (timeout / 1000.0):
        try:
            title = page.title()
        except Exception:
            title = ""

        is_cf_page = any(
            p.lower() in title.lower()
            for p in ["Just a moment", "Cloudflare", "Attention Required", "Security Check"]
        )

        # If title no longer indicates Cloudflare interstitial, verify page readiness
        if not is_cf_page and title != "":
            try:
                ready_state = page.evaluate("document.readyState")
                if ready_state in ("interactive", "complete"):
                    page.wait_for_timeout(1500)
                    return
            except Exception:
                return

        # Attempt to detect and solve interactive Turnstile iframe if present
        now = time.time()
        if now - last_click_time > 5.0:
            targets = [page] + list(page.frames)
            for target in targets:
                url = getattr(target, "url", "") or ""
                # Check frames from cloudflare or main challenge stage
                if "challenges.cloudflare.com" in url or "turnstile" in url or "challenge-platform" in url or is_cf_page:
                    for sel in [
                        "input[type='checkbox']",
                        ".ctp-checkbox-label",
                        "#challenge-stage",
                        "label.cb-lb",
                        "div#turnstile-wrapper",
                        "span.mark",
                    ]:
                        try:
                            loc = target.locator(sel)
                            if loc.count() > 0:
                                print(f"[playwright] Found Cloudflare Turnstile element ({sel}), clicking...")
                                loc.first.click(timeout=3000, force=True)
                                last_click_time = time.time()
                                time.sleep(3)
                                break
                        except Exception:
                            pass
                    if last_click_time > now:
                        break

        page.wait_for_timeout(1000)

    try:
        current_title = page.title()
    except Exception:
        current_title = "unknown"
    print(f"[playwright] Settle wait completed. Current page title: '{current_title}'")
    page.wait_for_timeout(2000)


def get_apkmirror_apk_playwright(variant_url, output_path, check_version_only=False):
    _ensure_playwright()
    from playwright.sync_api import sync_playwright
    try:
        from playwright_stealth import stealth_sync
        has_stealth = True
    except ImportError:
        has_stealth = False

    has_display = bool(os.environ.get("DISPLAY"))
    is_headless = not has_display if "HEADLESS" not in os.environ else (os.environ["HEADLESS"].lower() not in ("0", "false", "no"))
    print(f"[playwright] Launching Chromium (headless={is_headless}, display={os.environ.get('DISPLAY')}) to bypass Cloudflare...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=is_headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        try:
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                has_touch=False,
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                },
                accept_downloads=True,
            )
            page = ctx.new_page()
            if has_stealth:
                stealth_sync(page)
            else:
                page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
                )

            # Step 1: variant listing page
            print(f"[playwright] → {variant_url}")
            page.goto(variant_url, wait_until="domcontentloaded", timeout=60000)
            _pw_wait_for_cf(page)

            soup = BeautifulSoup(page.content(), "html.parser")
            detail_link, version_str = _find_detail_link(soup)
            if not detail_link:
                print("[playwright] No release link on variant page; trying dynamic catalog fallback...")
                detail_link, version_str = _find_fallback_detail_link()

            if check_version_only:
                if not version_str:
                    raise Exception(f"[playwright] Could not determine version (page title: '{page.title()}').")
                print(f"LATEST_VERSION={version_str}")
                return version_str

            if not detail_link:
                raise Exception(f"[playwright] Could not find download link on APKMirror variant page (page title: '{page.title()}').")

            # Step 2: APK detail page
            print(f"[playwright] → {detail_link}")
            page.goto(detail_link, wait_until="domcontentloaded", timeout=60000)
            _pw_wait_for_cf(page)

            detail_soup = BeautifulSoup(page.content(), "html.parser")
            dl_page = _find_download_page_link(detail_soup, detail_link)
            if not dl_page:
                raise Exception(f"[playwright] Could not find APK download button page (page title: '{page.title()}').")

            # Step 3: download-button confirmation page
            print(f"[playwright] → {dl_page}")
            page.goto(dl_page, wait_until="domcontentloaded", timeout=60000)
            _pw_wait_for_cf(page)

            dl_html_raw = page.content()
            dl_soup = BeautifulSoup(dl_html_raw, "html.parser")
            final_link = _find_final_link(dl_soup, dl_html_raw)

            if not final_link:
                raise Exception(f"[playwright] Could not extract final download URL from APKMirror (page title: '{page.title()}').")

            # Step 4: download inside the live browser session
            print(f"[playwright] Triggering APK download via browser session: {final_link}")
            downloads = []
            page.on("download", lambda dl: downloads.append(dl))

            a_tag = (
                page.query_selector("a#download-link")
                or page.query_selector("a[href*='download.php']")
                or page.query_selector("a.downloadButton")
                or page.query_selector("a.accent_bg")
                or page.query_selector("a[href*='key=']")
            )
            if a_tag:
                a_tag.click()
            else:
                page.evaluate(f"window.location.href = {json.dumps(final_link)}")

            # In case clicking download.php triggers a Cloudflare challenge
            _pw_wait_for_cf(page, timeout=30000)

            # Wait for download event
            dl_start = time.time()
            while not downloads and (time.time() - dl_start < 45):
                page.wait_for_timeout(1000)

            if not downloads:
                print(f"[playwright] Download not yet initiated; trying direct navigation to {final_link}...")
                page.evaluate(f"window.location.href = {json.dumps(final_link)}")
                _pw_wait_for_cf(page, timeout=30000)
                dl_start = time.time()
                while not downloads and (time.time() - dl_start < 45):
                    page.wait_for_timeout(1000)

            if not downloads:
                raise Exception(f"[playwright] Download did not start within timeout (page title: '{page.title()}').")

            download = downloads[0]
            print(f"[playwright] Saving APK ({download.suggested_filename}) to: {output_path}")
            download.save_as(output_path)
            return version_str
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Fast Version Discovery & Google Play Split Downloader
# ---------------------------------------------------------------------------

def check_version_feed():
    """Fetches latest Google Photos version instantly via APKMirror RSS feed (<500ms)."""
    try:
        import urllib.request
        feed_url = "https://www.apkmirror.com/apk/google-inc/photos/feed/"
        req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r"<title>Google Photos ([0-9.]+)", content)
            if match:
                ver = match.group(1).rstrip(".")
                print(f"[APKMirror Feed] Fast version discovery found: {ver}")
                return ver
    except Exception as e:
        print(f"[APKMirror Feed] Fast check notice (will fallback): {e}")
    return None


def download_google_play_splits(output_path):
    """
    Downloads Google Photos splits from Google Play using goopdl and merges them
    into a single universal standalone APK using REAndroid APKEditor.
    """
    goopdl_bin = shutil.which("goopdl")
    apkeditor_jar = os.environ.get("APKEDITOR_JAR", "APKEditor.jar")
    if not goopdl_bin or not os.path.exists(apkeditor_jar):
        print(f"[Google Play] Skipping: goopdl={bool(goopdl_bin)}, APKEditor.jar={os.path.exists(apkeditor_jar)}")
        return False, None

    splits_dir = Path("tmp_google_play_splits")
    if splits_dir.exists():
        shutil.rmtree(splits_dir, ignore_errors=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("\n=== [Source 1/2] Attempting Google Play direct download via goopdl ===")
        cmd = [
            goopdl_bin,
            "download",
            "com.google.android.apps.photos",
            "--splits",
            "-a", "arm64",
            "-o", str(splits_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            print(f"[Google Play] goopdl exited with {res.returncode}: {err}")
            return False, None

        split_apks = list(splits_dir.glob("*.apk"))
        if not split_apks:
            print("[Google Play] No split APKs were saved.")
            return False, None

        base_apk = next((f for f in split_apks if "base" in f.name.lower() or f.name == "com.google.android.apps.photos.apk"), split_apks[0])
        print(f"[Google Play] Downloaded {len(split_apks)} splits. Verifying base APK signature...")

        verify_script = Path(__file__).parent / "verify_signature.py"
        if verify_script.exists():
            v_res = subprocess.run([sys.executable, str(verify_script), str(base_apk)], capture_output=True, text=True)
            if v_res.returncode != 0:
                print(f"[Google Play] Signature verification failed:\n{v_res.stdout}\n{v_res.stderr}")
                return False, None
            print("[Google Play] Signature verified: authentic Google Inc. binary.")

        print(f"[Google Play] Merging splits into universal APK with {apkeditor_jar}...")
        merge_cmd = ["java", "-jar", apkeditor_jar, "m", "-i", str(splits_dir), "-o", str(output_path)]
        m_res = subprocess.run(merge_cmd, capture_output=True, text=True)
        if m_res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1_000_000:
            print(f"[Google Play] Merge failed (exit code {m_res.returncode}): {m_res.stderr.strip()}")
            return False, None

        print(f"[Google Play] Merge successful: {output_path} ({os.path.getsize(output_path):,} bytes)")

        version_str = "unknown"
        aapt_bin = shutil.which("aapt")
        if not aapt_bin:
            android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
            if android_home:
                candidates = list(Path(android_home).glob("build-tools/*/aapt"))
                if candidates:
                    aapt_bin = str(sorted(candidates, reverse=True)[0])
        if aapt_bin:
            aapt_res = subprocess.run([aapt_bin, "dump", "badging", str(output_path)], capture_output=True, text=True)
            v_match = re.search(r"versionName='([^']+)'", aapt_res.stdout)
            if v_match:
                version_str = v_match.group(1)

        return True, version_str

    except Exception as e:
        print(f"[Google Play] Download/merge error: {e}")
        return False, None
    finally:
        shutil.rmtree(splits_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Download Google Photos APK from APKMirror or Google Play")
    parser.add_argument("--direct-url", type=str, help="Skip scraping; download this URL directly")
    parser.add_argument("--variant-url", type=str, default=DEFAULT_VARIANT_URL)
    parser.add_argument("--output", type=str, default="google-photos.apk")
    parser.add_argument("--check-version", action="store_true")
    parser.add_argument("--retries", type=int, default=3, help="Max retry attempts for scraping (default: 3)")
    args = parser.parse_args()

    # ---- Fast version check shortcut ----
    if args.check_version:
        feed_ver = check_version_feed()
        if feed_ver:
            print(f"apk_version={feed_ver}")
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(f"apk_version={feed_ver}\n")
            return

    # ---- direct URL shortcut ----
    if args.direct_url:
        print(f"Downloading direct URL: {args.direct_url}")
        download_file(args.direct_url, args.output)
        version_str = "unknown"
    else:
        # Try Google Play download + merge first if not just checking version
        if not args.check_version:
            gp_success, gp_ver = download_google_play_splits(args.output)
            if gp_success:
                version_str = gp_ver or "unknown"
                if "GITHUB_OUTPUT" in os.environ and version_str:
                    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                        f.write(f"apk_version={version_str}\n")
                return

            print("[Downloader] Falling back to [Source 2/2] APKMirror standalone APK...")

        version_str = "unknown"
        success = False
        last_error = None
        for attempt in range(1, args.retries + 1):
            print(f"\n=== Download attempt {attempt}/{args.retries} ===")
            # Try fast path first, fall back to Playwright
            try:
                if args.check_version:
                    version_str = get_apkmirror_apk(args.variant_url, None, check_version_only=True)
                    if version_str:
                        success = True
                        break
                else:
                    version_str = get_apkmirror_apk(args.variant_url, args.output)
                    if os.path.exists(args.output) and os.path.getsize(args.output) > 1_000_000:
                        success = True
                        break
            except Exception as e:
                print(f"[Attempt {attempt}] Direct scrape failed: {e}")
                last_error = e

            # Fall back to Playwright if direct failed
            try:
                print(f"[Attempt {attempt}] Retrying with Playwright…")
                if args.check_version:
                    version_str = get_apkmirror_apk_playwright(args.variant_url, None, check_version_only=True)
                    if version_str:
                        success = True
                        break
                else:
                    version_str = get_apkmirror_apk_playwright(args.variant_url, args.output)
                    if os.path.exists(args.output) and os.path.getsize(args.output) > 1_000_000:
                        success = True
                        break
            except Exception as e2:
                print(f"[Attempt {attempt}] Playwright scrape failed: {e2}")
                last_error = e2

            if attempt < args.retries:
                backoff = 10 * attempt
                print(f"Waiting {backoff}s before next attempt...")
                time.sleep(backoff)

        if not success:
            print(f"\nAll {args.retries} download attempts failed! Last error: {last_error}")
            if not args.check_version:
                print("Pass --direct-url or trigger the workflow with a direct APK link.")
            sys.exit(1)

        if args.check_version:
            print(f"apk_version={version_str}")
            if "GITHUB_OUTPUT" in os.environ and version_str:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(f"apk_version={version_str}\n")
            return

    # ---- validate download ----
    if os.path.exists(args.output) and os.path.getsize(args.output) > 1_000_000:
        print(
            f"Successfully downloaded {args.output} "
            f"({os.path.getsize(args.output):,} bytes)"
        )
        # Verify cryptographic signature
        verify_script = Path(__file__).parent / "verify_signature.py"
        if verify_script.exists():
            print("Cryptographically validating downloaded APK...")
            subprocess.run([sys.executable, str(verify_script), str(args.output)], check=True)

        if "GITHUB_OUTPUT" in os.environ and version_str:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"apk_version={version_str}\n")
    else:
        print("Downloaded file is missing or too small!")
        sys.exit(1)


if __name__ == "__main__":
    main()
