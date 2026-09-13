#!/usr/bin/env python3
"""
Sync and Detect New Google Photos Models
========================================
Tool to automatically diff official Google Photos ML models and MDD manifests
against the repository manifest, identify new or updated models, and package
release archives.
"""

import os
import sys
import json
import base64
import hashlib
import zipfile
import argparse
import subprocess
import xml.etree.ElementTree as ET

SRC_PKG = "com.google.android.apps.photos"
DST_PKG = "app.morphe.android.apps.photos"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
MANIFEST_PATH = os.path.join(REPO_ROOT, "models_manifest.json")

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip(), res.returncode

def get_adb_device(target=None):
    if target:
        return f"adb -s {target}"
    out, _ = run_cmd("adb devices | grep -E 'device$' | head -n 1 | cut -f 1")
    if out:
        return f"adb -s {out}"
    return "adb"

def run_su(adb_cmd, shell_cmd):
    escaped = shell_cmd.replace('"', '\\"')
    out, code = run_cmd(f"{adb_cmd} shell \"su -c \\\"{escaped}\\\"\"")
    return out

def safe_b64decode(s):
    if not s:
        return b""
    s = s.strip()
    return base64.b64decode(s + "=" * (-len(s) % 4))

def main():
    parser = argparse.ArgumentParser(description="Diff and sync Google Photos ML models.")
    parser.add_argument("--device", help="Target ADB device (e.g. 192.168.1.4:5555)")
    parser.add_argument("--diff-only", action="store_true", help="Only check for diffs without exporting")
    parser.add_argument("--output-zip", default="/tmp/photos_models.zip", help="Output path for models zip")
    args = parser.parse_args()

    adb = get_adb_device(args.device)
    print(f"[*] Using ADB target: {adb}")

    # Check root access
    whoami = run_su(adb, "whoami")
    if "root" not in whoami:
        print("[!] Error: Root access required on target device to read official Photos app data.")
        sys.exit(1)

    print("[*] Inspecting official Google Photos MDD storage...")
    src_public = f"/data/data/{SRC_PKG}/files/datadownload/shared/public"
    raw_files = run_su(adb, f"ls -1 {src_public}")
    device_models = [f.strip() for f in raw_files.split("\n") if f.strip()]
    print(f"[+] Found {len(device_models)} model files on device.")

    # Load local manifest
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r") as f:
            manifest = json.load(f)
    else:
        manifest = {"manifest_version": 1, "models_count": 0, "features": {}}

    known_count = manifest.get("models_count", 0)
    print(f"[*] Local repository manifest has {known_count} models (version {manifest.get('manifest_version', 1)}).")

    # Check MDD groups
    src_prefs = f"/data/data/{SRC_PKG}/shared_prefs"
    raw_groups_xml = run_su(adb, f"cat {src_prefs}/gms_icing_mdd_groups.xml")
    if not raw_groups_xml or "<map>" not in raw_groups_xml:
        print("[!] Warning: Could not read gms_icing_mdd_groups.xml from official app.")
        filegroups = []
    else:
        tree = ET.fromstring(raw_groups_xml)
        filegroups = []
        for elem in tree.findall("string"):
            name = elem.get("name")
            if name:
                try:
                    decoded = safe_b64decode(name).decode("utf-8", errors="ignore")
                    filegroups.append(decoded)
                except Exception:
                    pass
        print(f"[+] Found {len(filegroups)} registered MDD filegroups on device.")

    diff_count = len(device_models) - known_count
    if diff_count > 0:
        print(f"\n[★] ALERT: Found {diff_count} NEW model(s) on device!")
    elif diff_count == 0:
        print("\n[✓] All models match current repository manifest count.")
    else:
        print(f"\n[-] Device has fewer models ({len(device_models)}) than repository ({known_count}).")

    if args.diff_only:
        print("[*] Diff-only completed.")
        return

    # If exporting / packaging:
    print(f"\n[*] Exporting models and manifests to {args.output_zip}...")
    temp_dir = "/tmp/gp_models_staging"
    os.makedirs(os.path.join(temp_dir, "models"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "manifests"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "protodb"), exist_ok=True)

    # Pull models via tar stream for maximum speed
    print("[*] Streaming models from device...")
    stream_cmd = f"{adb} shell \"su -c \\\"tar -C {src_public} -cf - .\\\"\" | tar -C {temp_dir}/models -xf -"
    subprocess.run(stream_cmd, shell=True, check=True)

    # Pull and translate manifests
    print("[*] Translating MDD manifests for Morphe...")
    for mf in [
        "gms_icing_mdd_groups.xml",
        "gms_icing_mdd_shared_files.xml",
        "gms_icing_mdd_group_key_properties.xml",
        "gms_icing_mdd_shared_file_manager_metadata.xml",
        "gms_icing_mdd_migrations.xml",
        "gms_icing_mdd_manager_metadata.xml"
    ]:
        xml_content = run_su(adb, f"cat {src_prefs}/{mf}")
        if xml_content:
            # Replace package string
            translated = xml_content.replace(SRC_PKG, DST_PKG)
            with open(os.path.join(temp_dir, "manifests", mf), "w") as out_f:
                out_f.write(translated)

    # Create zip
    with zipfile.ZipFile(args.output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, temp_dir)
                zf.write(full, rel)

    # Compute sha256
    h = hashlib.sha256()
    with open(args.output_zip, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    new_sha256 = h.hexdigest()
    new_size = os.path.getsize(args.output_zip)

    # Update manifest
    manifest["models_count"] = len(os.listdir(os.path.join(temp_dir, "models")))
    if diff_count > 0:
        manifest["manifest_version"] = manifest.get("manifest_version", 1) + 1
    manifest["sha256"] = new_sha256
    manifest["file_size"] = new_size

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[✓] Successfully generated {args.output_zip} ({round(new_size / (1024*1024), 2)} MB)")
    print(f"[✓] Updated {MANIFEST_PATH} (version {manifest['manifest_version']}, SHA-256: {new_sha256})")

if __name__ == "__main__":
    main()
