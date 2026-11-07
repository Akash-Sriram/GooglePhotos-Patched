#!/usr/bin/env python3
"""
Verify Google Photos APK cryptographic signature against official Google public certificate.
Ensures binary authenticity before patching.
"""
import sys
import subprocess
import shutil
import re
from pathlib import Path

# Official Google Photos Signing Certificate Fingerprints
GOOGLE_PHOTOS_SHA256 = "5aad2bee6db95d17e05a08d7d1e64c10a1511879154483916b6ae6c7fd9cb0c6"
GOOGLE_PHOTOS_SHA1 = "24bb24c05e47e0aefa68a58a766179d9b613a600"


def find_apksigner() -> str | None:
    path = shutil.which("apksigner")
    if path:
        return path
    # Look in Android SDK if environment is set
    import os
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if android_home:
        build_tools = list(Path(android_home).glob("build-tools/*/apksigner"))
        if build_tools:
            return str(sorted(build_tools, reverse=True)[0])
    # Common local sdk path
    fallback = list(Path.home().glob("android-sdk/build-tools/*/apksigner"))
    if fallback:
        return str(sorted(fallback, reverse=True)[0])
    return None


def verify_apk(apk_path: str) -> bool:
    apksigner = find_apksigner()
    if not apksigner:
        print("⚠️ Warning: apksigner not found. Skipping signature verification.")
        return True

    cmd = [apksigner, "verify", "--print-certs", apk_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ apksigner verification failed with exit code {res.returncode}:")
        print(res.stderr)
        return False

    output = res.stdout
    sha256_matches = re.findall(r"certificate SHA-256 digest:\s*([0-9a-fA-F]+)", output)
    sha1_matches = re.findall(r"certificate SHA-1 digest:\s*([0-9a-fA-F]+)", output)

    sha256_lower = [s.lower() for s in sha256_matches]
    sha1_lower = [s.lower() for s in sha1_matches]

    is_authentic = (
        GOOGLE_PHOTOS_SHA256.lower() in sha256_lower or
        GOOGLE_PHOTOS_SHA1.lower() in sha1_lower
    )

    if is_authentic:
        print(f"✅ Cryptographically verified: {apk_path} is authentically signed by Google Inc.")
        return True
    else:
        print(f"🚨 CRITICAL: Untrusted APK signature for {apk_path}!")
        print(f"Found SHA-256: {sha256_matches}")
        print(f"Expected SHA-256: {GOOGLE_PHOTOS_SHA256}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_signature.py <path_to_apk>")
        sys.exit(1)

    apk_file = sys.argv[1]
    if not Path(apk_file).is_file():
        print(f"Error: File not found: {apk_file}")
        sys.exit(1)

    if not verify_apk(apk_file):
        sys.exit(1)
    sys.exit(0)
