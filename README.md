# Google Photos Patched

Automated builds of Google Photos patched via [Morphe Google Photos](https://github.com/Akash-Sriram/morphe-google-photos).

Rebuilt every 6 hours using clean nodpi base APKs from [APKMirror](https://www.apkmirror.com/apk/google-inc/photos/).

📥 **Downloads**: [Latest Release](https://github.com/Akash-Sriram/GooglePhotos-Patched/releases/latest)  
🔑 **Prerequisite**: [MicroG-RE](https://github.com/MorpheApp/MicroG-RE/releases/latest) *(required for non-root Google account sign-in)*

---

## 🎯 Features & Patch Set

This repository provides automated builds of patched Google Photos with Pixel backup spoofing, engine enhancements, and UI customizability:

* **Pixel Spoofing**: Unlimited Google Photos cloud backup at original quality and unlocked Pixel-exclusive editor features.
* **Flag Manager & Morphe Toolkit**: Accessible right from Photos Settings to toggle experimental Google features, video editor tools, and UI options.
* **AMOLED Dark Theme**: Deep pitch-black surfaces in dark mode for maximum contrast and OLED battery savings.
* **Media Engine & AI Fixes**: Ensures Magic Eraser, Portrait tools, and custom fonts download and function without mobile data restrictions.
* **DCIM & Backup Control**: Granular folder backup toggles so camera screenshots and non-camera folders aren't forced into backup.
* **In-App Updater**: Built-in silent check on launch notifying you when a newer patched release is ready on GitHub.
* **MicroG / GmsCore Support**: Enabled across all variants to guarantee Google account sign-in via [MicroG-RE](https://github.com/MorpheApp/MicroG-RE/releases/latest).

---

## ⚡ Upstream Updates & Auto-Fixes

* **Automated Builds**: The pipeline runs every 6 hours to detect, patch, and release new Google Photos stable versions.
* **Compatibility & Auto-Healing**: If a newer upstream Google Photos release introduces breaking obfuscation or changes that cause patches to fail, builds may temporarily pause or fail. Once the patch definitions are updated in [morphe-google-photos](https://github.com/Akash-Sriram/morphe-google-photos), the next scheduled workflow run will automatically pick up the fix and produce working builds—no manual reconfiguration needed.

---

## 📦 Package Flavors

| Package | Asset Name | Package ID | Target Audience & Usage |
|:---|:---|:---|:---|
| **Mod** *(Recommended)* | `GooglePhotos-v<ver>-mod.apk` | `app.morphe.android.apps.photos` | Non-root users. Installs side-by-side with official Google Photos. Features the Morphe pinwheel icon and "Photos" launcher label. Requires [MicroG-RE](https://github.com/MorpheApp/MicroG-RE/releases/latest) for sign-in. |
| **Original** | `GooglePhotos-v<ver>-original.apk` | `com.google.android.apps.photos` | Rooted users / custom ROMs without pre-installed Google Photos. Keeps stock package ID, official icon, and includes a Play Store auto-update blocker. Requires [MicroG-RE](https://github.com/MorpheApp/MicroG-RE/releases/latest) for sign-in. |
