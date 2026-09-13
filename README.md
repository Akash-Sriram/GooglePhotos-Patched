# Google Photos Patched

Automated builds of Google Photos patched with [De-Vanced](https://github.com/Akash-Sriram/De-Vanced).  
Pre-built APKs: [GitHub Releases](https://github.com/Akash-Sriram/GooglePhotos-Patched/releases/latest)  
*Requires [MicroG-RE](https://github.com/MorpheApp/MicroG-RE) or GmsCore for non-root Google account login.*

---

## ⚡ Features

| Feature | Details |
|---|---|
| **🚀 Unlimited Original Backup** | Lifetime unmetered original-quality cloud storage via Pixel XL spoofing. |
| **🧠 Auto AI Model Seeder** | In-app background downloader for all 72 TensorFlow Lite models (Magic Eraser, Portrait Blur, Sky, Moods) on any device (e.g. Galaxy S24) without root. |
| **🎨 Unlocked Pixel Editing** | Magic Eraser, Portrait Blur, Sky Replacements, Dynamic HDR, and Color Pop. |
| **👤 Account Avatar Bridge** | Full MicroG profile photo support across Toolbar, Bento Menu, and Account Switchers. |
| **📁 Independent DCIM Control** | Custom backup toggles for non-camera media (Screenshots, WhatsApp). |
| **🛠️ In-App Flag Manager** | Real-time Phenotype flag debugging and UI presets in `Settings > 🛠️ Morphe Flags`. |
| **🔄 In-App Auto Updater** | Checks for newer patched builds directly inside the app with one-tap download. |

---

## ⚙️ Automated Pipeline

- **Automatic Trigger**: Builds every 6 hours via GitHub Actions and instantly whenever a new release is published in [De-Vanced](https://github.com/Akash-Sriram/De-Vanced).
- **Source**: Scrapes and patches the latest official universal (nodpi) Google Photos releases from APKMirror.
