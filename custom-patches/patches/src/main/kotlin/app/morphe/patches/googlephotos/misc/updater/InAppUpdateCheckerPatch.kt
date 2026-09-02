package app.morphe.patches.googlephotos.misc.updater

import app.morphe.patcher.extensions.InstructionExtensions.addInstruction
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patcher.patch.stringOption
import app.morphe.patches.googlephotos.misc.extension.sharedExtensionPatch
import app.morphe.patches.shared.compat.AppCompatibilities

@Suppress("unused")
val inAppUpdateCheckerPatch = bytecodePatch(
    name = "Enable in-app update checker",
    description = "Checks for newer patched Google Photos releases on GitHub and prompts to update.",
    default = true,
) {
    compatibleWith(AppCompatibilities.GOOGLE_PHOTOS)
    extendWith(sharedExtensionPatch)

    val releaseApiUrl by stringOption(
        key = "releaseApiUrl",
        default = "https://api.github.com/repos/Akash-Sriram/GooglePhotos-Patched/releases/latest",
        title = "GitHub Release API URL",
        description = "Endpoint to check for the latest patched Google Photos APK release.",
        required = true,
    )

    execute {
        HomeActivityOnCreateFingerprint.method.addInstruction(
            0,
            """
                const-string v0, "$releaseApiUrl"
                invoke-static {p0, v0}, Lapp/morphe/extension/shared/updater/GitHubReleaseChecker;->checkUpdateOnStartup(Landroid/content/Context;Ljava/lang/String;)V
            """.trimIndent()
        )
    }
}

