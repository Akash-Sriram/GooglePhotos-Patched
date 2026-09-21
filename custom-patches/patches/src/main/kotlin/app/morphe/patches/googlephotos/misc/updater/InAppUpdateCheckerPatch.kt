package app.morphe.patches.googlephotos.misc.updater

import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patcher.patch.resourcePatch
import app.morphe.patcher.patch.stringOption
import app.morphe.patches.googlephotos.misc.extension.sharedExtensionPatch
import app.morphe.patches.shared.compat.AppCompatibilities
import org.w3c.dom.Element

val inAppUpdateCheckerResourcePatch = resourcePatch {
    execute {
        document("AndroidManifest.xml").use { document ->
            val manifestNode = document.getElementsByTagName("manifest").item(0)
            val existingPermissions = document.getElementsByTagName("uses-permission")
            val alreadyAdded = (0 until existingPermissions.length).any { i ->
                (existingPermissions.item(i) as? Element)?.getAttribute("android:name") == "android.permission.REQUEST_INSTALL_PACKAGES"
            }
            if (!alreadyAdded) {
                val permissionNode = document.createElement("uses-permission")
                permissionNode.setAttribute("android:name", "android.permission.REQUEST_INSTALL_PACKAGES")
                manifestNode.appendChild(permissionNode)
            }
        }
    }
}

@Suppress("unused")
val inAppUpdateCheckerPatch = bytecodePatch(
    name = "Enable in-app update checker",
    description = "Checks for newer patched Google Photos releases on GitHub and prompts to update.",
    default = true,
) {
    compatibleWith(AppCompatibilities.GOOGLE_PHOTOS)
    dependsOn(inAppUpdateCheckerResourcePatch)
    dependsOn(sharedExtensionPatch)


    val releaseApiUrl by stringOption(
        key = "releaseApiUrl",
        default = "https://api.github.com/repos/Akash-Sriram/GooglePhotos-Patched/releases/latest",
        title = "GitHub Release API URL",
        description = "Endpoint to check for the latest patched Google Photos APK release.",
        required = true,
    )

    execute {
        HomeActivityOnCreateFingerprint.method.addInstructions(
            0,
            """
                const-string v0, "$releaseApiUrl"
                invoke-static {p0, v0}, Lapp/morphe/extension/shared/updater/GitHubReleaseChecker;->checkUpdateOnStartup(Landroid/content/Context;Ljava/lang/String;)V
            """.trimIndent()
        )
    }
}

