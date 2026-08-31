# Google Photos Patched

Automated builds of Google Photos patched with [De-Vanced](https://github.com/Akash-Sriram/De-Vanced).  
Pre-built APKs: [GitHub Releases](https://github.com/Akash-Sriram/GooglePhotos-Patched/releases/latest)  
*Requires [MicroG-RE](https://github.com/MorpheApp/MicroG-RE) for non-root Google account login.*

## ⚡ Features

| Feature | Details |
|---|---|
| **🚀 Unlimited Original Backup** | Lifetime unmetered original-quality cloud storage via Pixel XL spoofing. |
| **🎨 Unlocked Pixel Editing** | Magic Eraser, Portrait Blur, Sky Replacements, Unblur, Dynamic HDR, and Color Pop. |
| **👤 Account Avatar Bridge** | Full MicroG profile photo support across Toolbar, Bento, and Switchers with smooth animations. |
| **📁 Independent DCIM Control** | Custom backup toggles for non-camera media (Screenshots, WhatsApp). |
| **🛠️ In-App Flag Manager** | Real-time Phenotype flag debugging and UI customization in `Settings > 🛠️ Morphe Flags`. |
| **🔄 In-App Auto Updater** | Checks for newer patched builds directly inside the app with one-tap download. |

## ⚙️ Automated Pipeline

- **Trigger**: Automated GitHub Actions cron runs every **6 hours**.
- **Source**: Scrapes latest official arm64 APKs directly from APKMirror.
- **Engine**: Compiles the latest patches from [Akash-Sriram/De-Vanced](https://github.com/Akash-Sriram/De-Vanced) and signs with release keystore.

