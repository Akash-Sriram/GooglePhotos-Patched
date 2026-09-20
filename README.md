# Google Photos Patched

Automated builds of Google Photos patched with [Morphe Google Photos](https://github.com/Akash-Sriram/morphe-google-photos).  
Pre-built APKs: [GitHub Releases](https://github.com/Akash-Sriram/GooglePhotos-Patched/releases/latest)  
*Requires [MicroG-RE](https://github.com/MorpheApp/MicroG-RE) or GmsCore for non-root Google account login.*

---

## 📦 Choose Your Package Flavor (Both Non-Root)

Every release provides two ready-to-install, 100% non-root variants. Choose the one that matches your device:

| Package | Asset Name | Package ID | Best For | Play Store Block |
|:---|:---|:---|:---|:---:|
| **Mod Package** | `GooglePhotos-v<ver>-mod.apk` | `app.morphe.android.apps.photos` | **Most Users.** Phones where Google Photos is pre-installed as an unremovable system app. Installs side-by-side without conflicts. | Not needed *(Play Store ignores mod package)* |
| **Original Package** | `GooglePhotos-v<ver>-original.apk` | `com.google.android.apps.photos` | Phones **without** Google Photos pre-installed (or completely uninstalled via ADB / custom ROM). Retains stock package name. | **Active** *(Version code spoofed so Play Store cannot overwrite)* |

> [!TIP]
> **Not sure which to pick?** Choose the **Mod Package (`-mod.apk`)**. It works on any device and will never conflict with factory-installed apps.

---

## ✨ Key Highlights

- **🚀 Unlimited Original Backup**: Lifetime unmetered original-quality storage via Pixel XL hardware spoofing.
- **🎨 Unlocked Pixel Editing Tools**: Magic Eraser, Portrait Blur, Sky Replacements, Dynamic HDR, and AI presets.
- **🛠️ In-App Flag Manager**: Real-time experimental feature flags and UI presets in `Settings > 🛠️ Morphe Flags`.
- **🔄 Smart In-App Updater**: Automatically detects your installed flavor (`-mod` or `-original`) and updates directly inside the app.

👉 *For the full list of patches, Smali bytecode hooks, and curated Phenotype flags, see [Morphe Google Photos](https://github.com/Akash-Sriram/morphe-google-photos).*

---

## 🚀 Installation Guide

1. **Install MicroG-RE**:
   Download and install [MicroG-RE (GmsCore)](https://github.com/MorpheApp/MicroG-RE/releases/latest). This is required for Google account login on patched builds.
2. **Download Patched Google Photos**:
   Head to the **[Latest Release](https://github.com/Akash-Sriram/GooglePhotos-Patched/releases/latest)** and download your chosen APK:
   - `GooglePhotos-v...-mod.apk` *(recommended for most devices)*
   - `GooglePhotos-v...-original.apk` *(for clean/uninstalled devices)*
3. **Install & Sign In**:
   Open the installed app, tap the profile icon, and sign in to your Google Account.

---

## ❓ Frequently Asked Questions

<details>
<summary><b>Do I need a rooted phone?</b></summary>
<br>
<b>No.</b> Both the Mod Package and Original Package are designed for non-rooted devices. You only need <a href="https://github.com/MorpheApp/MicroG-RE/releases/latest">MicroG-RE</a> installed to handle account authentication.
</details>

<details>
<summary><b>Will Google Play Store overwrite my patched app?</b></summary>
<br>
<ul>
  <li><b>Mod Package:</b> Google Play Store cannot see or update it because it uses a custom package ID (<code>app.morphe.android.apps.photos</code>).</li>
  <li><b>Original Package:</b> The build includes the <i>Disable Play Store updates</i> patch, which sets the version code to maximum so the Play Store never flags it for an update.</li>
</ul>
</details>

<details>
<summary><b>How does the In-App Updater work?</b></summary>
<br>
The app checks GitHub Releases in the background on startup. When an update is available:
<ul>
  <li>It automatically detects whether you are running the <b>Mod</b> or <b>Original</b> package and downloads the correct APK.</li>
  <li>It displays a download progress bar and prompts the system installer to upgrade without losing your settings or local data.</li>
</ul>
</details>

<details>
<summary><b>Where are the patches maintained?</b></summary>
<br>
All patch code, bytecode hooks, and flag definitions are developed and maintained in the <a href="https://github.com/Akash-Sriram/morphe-google-photos">Morphe Google Photos</a> repository.
</details>

---

## ⚙️ Automated Pipeline

- **Trigger**: Runs every 6 hours via GitHub Actions and triggers automatically whenever a new release is published in [Morphe Google Photos](https://github.com/Akash-Sriram/morphe-google-photos).
- **Base APKs**: Scraped from official universal (`nodpi`) Google Photos releases on APKMirror.
- **Signing**: Automated release signing with `zipalign`, zip header alignment fix, and `apksigner`.
