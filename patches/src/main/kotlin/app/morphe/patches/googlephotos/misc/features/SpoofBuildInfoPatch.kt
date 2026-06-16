/*
 * Forked from:
 * https://gitlab.com/ReVanced/revanced-patches/-/blob/main/patches/src/main/kotlin/app/revanced/patches/googlephotos/misc/features/SpoofBuildInfoPatch.kt
 */
package app.morphe.patches.googlephotos.misc.features

import app.morphe.patches.all.misc.build.BuildInfo
import app.morphe.patches.all.misc.build.baseSpoofBuildInfoPatch

// Spoof build info to Google Pixel XL so backups get unlimited storage.
val spoofBuildInfoPatch = baseSpoofBuildInfoPatch {
    BuildInfo(
        brand = "google",
        manufacturer = "Google",
        device = "marlin",
        product = "marlin",
        hardware = "marlin",
        id = "QP1A.191005.007.A3",
        model = "Pixel XL",
        fingerprint = "google/marlin/marlin:10/QP1A.191005.007.A3/5972272:user/release-keys",
    )
}
