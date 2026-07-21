# Morphe Photo Patches

Morphe patches for Google Photos. 

Includes a custom fix for the **DCIM folders backup control** patch, updating it to support the new standards of newer Google Photos versions while maintaining backward compatibility.

## Features

- **Enable DCIM folders backup control (with new standard fix)**: Disables always-on backup for the Camera and other DCIM folders, allowing you to control backup for each folder individually.
- **Spoof features**: Spoofs the device as a Google Pixel to unlock Pixel-exclusive features (like unlimited storage backup).
- **GmsCore support**: Redirects GMS calls to GmsCore (`app.revanced.android.gms`) to allow the patched Google Photos app to run without root.
- **Fix selected account persistence**: Prevents Google Photos from losing your active Google Account after cold starts on non-rooted devices.
