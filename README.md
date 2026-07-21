# Morphe Photo Patches

Morphe patches for Google Photos to enable Pixel-exclusive features (such as unlimited backup), control DCIM folders backup, bypass GmsCore restrictions on non-rooted devices, and maintain account login persistence.

## Features

- **Enable DCIM folders backup control**: Allows you to control backup for the Camera and other DCIM folders individually instead of backing up everything.
- **Spoof features**: Spoofs the device as a Google Pixel to unlock Pixel-exclusive features (like unlimited storage backup).
- **GmsCore support**: Redirects GMS calls to GmsCore (`app.revanced.android.gms`) to allow the patched Google Photos app to run without root.
- **Fix selected account persistence**: Prevents Google Photos from losing your active Google Account after cold starts on non-rooted devices.

## Building

Ensure you have Java 17+ installed, and run:
```bash
./gradlew build
```
This generates `patches/build/libs/patches-[version].mpp` which you can load directly into the Morphe Manager or CLI patcher!

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
