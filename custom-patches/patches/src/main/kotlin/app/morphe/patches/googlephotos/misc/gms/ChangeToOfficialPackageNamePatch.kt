package app.morphe.patches.googlephotos.misc.gms

import app.morphe.patcher.patch.resourcePatch
import app.morphe.patches.googlephotos.misc.gms.Constants.MORPHE_PHOTOS_PACKAGE_NAME
import app.morphe.patches.shared.compat.AppCompatibilities
import app.morphe.patches.shared.misc.gms.PackageNameConfig

@Suppress("unused")
val changeToOfficialPackageNamePatch = resourcePatch(
    name = "Change to official package name",
    description = "Keeps the official package name (com.google.android.apps.photos) instead of renaming to " +
        "$MORPHE_PHOTOS_PACKAGE_NAME. Enable this only if Google Photos is uninstalled via ADB or installed " +
        "as a system app with root. When selecting this, also select 'Disable Play Store updates'.",
    default = false,
) {
    category("Experimental")
    compatibleWith(AppCompatibilities.GOOGLE_PHOTOS)

    execute {
        PackageNameConfig.useOfficialPackageName = true
    }
}
