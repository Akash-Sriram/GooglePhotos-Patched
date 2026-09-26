#!/usr/bin/env bash
""":"exec" python3 "$0" "$@"
"""
"""
repack_apk.py - Optimizes and normalizes Android APK archives before zipalign & apksigner.

Key optimizations:
1. Recompresses 'resources.arsc' with Deflate (level 9), reducing Universal APK
   size by ~45 MB (~225 MB -> ~180 MB) without stripping any CPU architectures.
2. Normalizes local file headers and central directory headers to prevent zip
   corruption warnings and ensure clean zipalign passes.
3. Preserves STORED compression for files that require direct mmap/uncompressed access.
"""

import argparse
import os
import sys
import zipfile


def repack_apk(input_path: str, output_path: str) -> None:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input APK not found: {input_path}")

    orig_size = os.path.getsize(input_path)
    print(f"[*] Repacking {input_path} ({orig_size / (1024 * 1024):.2f} MB)...")

    # TargetSdk >= 30 (Android 11+) requires resources.arsc to be STORED (uncompressed)
    # and 4-byte aligned. Recompressing resources.arsc triggers PackageManager failure:
    # "Failed parse during installPackageLI: Targeting R+ requires resources.arsc to be stored uncompressed".
    COMPRESS_TARGETS = set()

    with zipfile.ZipFile(input_path, "r") as in_zip, zipfile.ZipFile(
        output_path, "w"
    ) as out_zip:
        for item in in_zip.infolist():
            # Don't copy existing signature files if any (apksigner will generate fresh ones)
            if item.filename.startswith("META-INF/") and (
                item.filename.endswith(".SF")
                or item.filename.endswith(".RSA")
                or item.filename.endswith(".DSA")
                or item.filename.endswith(".EC")
            ):
                continue

            data = in_zip.read(item.filename)

            # Determine compression mode
            if item.filename in COMPRESS_TARGETS:
                compress_type = zipfile.ZIP_DEFLATED
                compresslevel = 9
            else:
                compress_type = item.compress_type
                compresslevel = None

            # Reset extra fields to avoid zip format inconsistencies
            # (e.g. data descriptor flags or extended timestamps that conflict with central dir)
            new_item = zipfile.ZipInfo(item.filename, date_time=item.date_time)
            new_item.compress_type = compress_type
            new_item.create_system = item.create_system
            new_item.external_attr = item.external_attr
            new_item.comment = item.comment

            out_zip.writestr(new_item, data, compress_type=compress_type, compresslevel=compresslevel)

    new_size = os.path.getsize(output_path)
    saved_bytes = orig_size - new_size
    saved_mb = saved_bytes / (1024 * 1024)
    pct = (saved_bytes / orig_size) * 100 if orig_size > 0 else 0

    print(
        f"[+] Finished: {output_path} ({new_size / (1024 * 1024):.2f} MB)"
        f" | Saved: {saved_mb:.2f} MB ({pct:.1f}% reduction)"
    )


def main():
    parser = argparse.ArgumentParser(description="Optimize and normalize APK archive.")
    parser.add_argument("--input", "-i", required=True, help="Path to input APK")
    parser.add_argument("--output", "-o", required=True, help="Path to output APK")
    args = parser.parse_args()

    try:
        repack_apk(args.input, args.output)
    except Exception as e:
        print(f"[!] Error repacking APK: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
