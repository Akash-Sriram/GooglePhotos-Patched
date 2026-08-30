# Google Photos Patched

Automated builds of Google Photos patched with [Akash-Sriram/De-Vanced](https://github.com/Akash-Sriram/De-Vanced).

## Workflow

- **Base APK Source**: [APKMirror (nodpi, arm64-v8a)](https://www.apkmirror.com/apk/google-inc/photos/variant-%7B%22dpis_slug%22%3A%5B%22nodpi%22%5D%2C%22arches_slug%22%3A%5B%22arm64-v8a%22%2C%22armeabi-v7a%22%2C%22x86%22%2C%22x86_64%22%5D%7D/)
- **Patcher**: Automatically compiles latest patches from `Akash-Sriram/De-Vanced` and patches via Morphe CLI.
- **Schedule**: Checks for updates and builds automatically every 6 hours.

## Download

Get the latest APK from [Releases](https://github.com/Akash-Sriram/GooglePhotos-Patched/releases).

*Requires [MicroG / GmsCore](https://github.com/ReVanced/GmsCore/releases) for Google account login.*
