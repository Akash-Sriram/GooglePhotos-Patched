/*
 * Forked from:
 * https://gitlab.com/ReVanced/revanced-patches/-/blob/main/patches/src/main/kotlin/app/revanced/patches/googlephotos/misc/gms/GmsCoreSupportPatch.kt
 */
package app.morphe.patches.googlephotos.misc.gms

import app.morphe.patches.googlephotos.misc.extension.sharedExtensionPatch
import app.morphe.patches.shared.compat.AppCompatibilities
import app.morphe.patches.googlephotos.misc.gms.Constants.MORPHE_PHOTOS_PACKAGE_NAME
import app.morphe.patches.googlephotos.misc.gms.Constants.PHOTOS_PACKAGE_NAME
import app.morphe.patches.googlephotos.misc.gms.HomeActivityOnCreateFingerprint
import app.morphe.patches.shared.misc.gms.PackageNameConfig
import app.morphe.patches.shared.misc.gms.gmsCoreSupportPatch
import app.morphe.patches.shared.misc.settings.preference.BasePreferenceScreen
import app.morphe.patches.shared.misc.settings.preference.PreferenceScreenPreference
import app.morphe.patcher.extensions.InstructionExtensions.addInstruction
import app.morphe.patcher.extensions.InstructionExtensions.getInstruction
import app.morphe.patcher.extensions.InstructionExtensions.replaceInstruction
import app.morphe.util.asSequence
import app.morphe.util.findMutableMethodOf
import app.morphe.util.getNode
import app.morphe.util.getReference
import app.morphe.util.indexOfFirstInstructionOrThrow
import app.morphe.util.returnEarly
import com.android.tools.smali.dexlib2.iface.reference.MethodReference
import com.android.tools.smali.dexlib2.iface.reference.StringReference
import org.w3c.dom.Element

@Suppress("unused")
val gmsCoreSupportPatch = gmsCoreSupportPatch(
    fromPackageName = PHOTOS_PACKAGE_NAME,
    toPackageName = MORPHE_PHOTOS_PACKAGE_NAME,
    mainActivityOnCreateFingerprint = HomeActivityOnCreateFingerprint,
    extensionPatch = sharedExtensionPatch,
    gmsCoreSupportResourcePatchFactory = ::gmsCoreSupportResourcePatch,
    executeBlock = {
        // 1) Combined single pass over all classes:
        //    - Bundle Google Play Services availability & signature check hooks
        //    - Relax MDD and WorkManager network constraints from UNMETERED/NOT_ROAMING to CONNECTED
        classDefForEach { classDef ->
            val mutableClass by lazy { mutableClassDefBy(classDef) }

            classDef.methods.forEach classLoop@{ method ->
                // Check A: Google Play Services availability check
                val isAvailabilityCheck = method.returnType == "I" &&
                    (
                        (method.parameterTypes.size == 2 && method.parameterTypes[0] == "Landroid/content/Context;" && method.parameterTypes[1] == "I") ||
                        (method.parameterTypes.size == 1 && method.parameterTypes[0] == "Landroid/content/Context;")
                    )
                if (isAvailabilityCheck) {
                    val impl = method.implementation
                    if (impl != null && impl.instructions.any { instr ->
                        val str = (instr.getReference<com.android.tools.smali.dexlib2.iface.reference.StringReference>())?.string
                        str?.contains("android.gms") == true || str?.contains("GooglePlayServices") == true
                    }) {
                        mutableClass.findMutableMethodOf(method).returnEarly(0)
                        return@classLoop
                    }
                }

                // Check B: PackageInfo signature verification
                val isSignatureCheck = method.returnType == "Z" &&
                    method.parameterTypes.size in 1..2 &&
                    method.parameterTypes[0] == "Landroid/content/pm/PackageInfo;"
                if (isSignatureCheck) {
                    mutableClass.findMutableMethodOf(method).returnEarly(true)
                    return@classLoop
                }

                // Check C: WorkManager / MDD network constraints
                val implementation = method.implementation ?: return@classLoop
                implementation.instructions.forEachIndexed { index, instruction ->
                    val fieldRef = (instruction as? com.android.tools.smali.dexlib2.iface.instruction.ReferenceInstruction)?.reference as? com.android.tools.smali.dexlib2.iface.reference.FieldReference
                        ?: return@forEachIndexed

                    if (fieldRef.definingClass == "Landroidx/work/NetworkType;" &&
                        (fieldRef.name == "UNMETERED" || fieldRef.name == "NOT_ROAMING")) {
                        val register = (instruction as com.android.tools.smali.dexlib2.iface.instruction.OneRegisterInstruction).registerA
                        mutableClass.findMutableMethodOf(method).replaceInstruction(
                            index,
                            "sget-object v$register, Landroidx/work/NetworkType;->CONNECTED:Landroidx/work/NetworkType;",
                        )
                    }
                }
            }
        }

        // 2) Fix Locked Folder (Mars) cloud backup: translate Mars-related internal package-name
        //    strings in DEX bytecode from the official package name to the mod package name.
        //
        //    Background: patchManifest() in the shared GmsCore patch renames the ContentProvider
        //    authority *declarations* in AndroidManifest.xml, e.g.:
        //      "com.google.android.apps.photos.mars.contentprovider.local_locked_media"
        //    →  "app.morphe.android.apps.photos.mars.contentprovider.local_locked_media"
        //    However, the DEX bytecode constructs content:// URIs and Intent actions using the
        //    original package name, so the OS fails to resolve the provider and the entire
        //    Locked Folder pipeline (backup eligibility, auth handshake, data sync) breaks.
        //    This pass re-aligns those strings with the renamed authorities in the manifest.
        //    Only execute this transformation when package renaming is enabled.
        if (PackageNameConfig.isPackageNameChangeEnabled) {
            val targetPackageName = PackageNameConfig.effectivePackageName.ifEmpty { MORPHE_PHOTOS_PACKAGE_NAME }
            val marsPackagePrefixes = listOf(
                "$PHOTOS_PACKAGE_NAME.mars.",
                "content://$PHOTOS_PACKAGE_NAME.mars.",
            )
            classDefForEach { classDef ->
                val mutableClass by lazy { mutableClassDefBy(classDef) }

                classDef.methods.forEach marsLoop@{ method ->
                    val implementation = method.implementation ?: return@marsLoop

                    val mutableMethod by lazy { mutableClass.findMutableMethodOf(method) }

                    implementation.instructions.forEachIndexed { index, instruction ->
                        val stringRef =
                            (instruction as? com.android.tools.smali.dexlib2.iface.instruction.formats.Instruction21c)
                                ?.reference as? StringReference
                                ?: return@forEachIndexed

                        val original = stringRef.string
                        val transformed = marsPackagePrefixes
                            .firstOrNull { original.startsWith(it) }
                            ?.let { original.replace(PHOTOS_PACKAGE_NAME, targetPackageName) }
                            ?: return@forEachIndexed

                        mutableMethod.replaceInstruction(
                            index,
                            com.android.tools.smali.dexlib2.builder.instruction.BuilderInstruction21c(
                                com.android.tools.smali.dexlib2.Opcode.CONST_STRING,
                                (instruction as com.android.tools.smali.dexlib2.iface.instruction.OneRegisterInstruction).registerA,
                                com.android.tools.smali.dexlib2.immutable.reference.ImmutableStringReference(transformed),
                            ),
                        )
                    }
                }
            }
        }

        // 3) Disable the AccountValidityMonitor check that runs on resume.
        AccountValidityMonitorCheckFingerprint.method.addInstruction(
            0,
            "return-void",
        )

        // 4) Keep the frictionless eligibility result intact, but prevent the
        //    MicroG failure path from clearing the selected account.
        FrictionlessEligibilityFingerprint.method.apply {
            val clearSelectedAccountIndex = indexOfFirstInstructionOrThrow {
                getReference<MethodReference>()?.let { ref ->
                    ref.name == "o" &&
                        ref.returnType == "V" &&
                        ref.parameterTypes.toList() == listOf("I")
                } == true
            }
            val accountHandlerClass = getInstruction(clearSelectedAccountIndex)
                .getReference<MethodReference>()!!
                .definingClass

            replaceInstruction(clearSelectedAccountIndex, "invoke-virtual {p0}, $accountHandlerClass->p()V")
        }

        // 5) Hook CurrentLocationMixin.a() to immediately obtain device location and animate map camera.
        CurrentLocationMixinFingerprint.method.apply {
            addInstruction(
                0,
                "invoke-static {p0}, Lapp/morphe/extension/shared/patches/GmsCoreSupportPatch;->handleCurrentLocation(Ljava/lang/Object;)V",
            )
            addInstruction(
                1,
                "return-void",
            )
        }
    },
) {
    compatibleWith(AppCompatibilities.GOOGLE_PHOTOS)
}

/**
 * Minimal preference screen used only to satisfy the shared GmsCore support
 * resource patch API. Google Photos does not currently expose a dedicated
 * Morphe settings UI, so the committed screen is intentionally a no-op.
 */
private object DummyPreferenceScreen : BasePreferenceScreen() {
    val SCREEN = Screen(
        key = "morphe_settings_googlephotos_screen_1_misc",
        summaryKey = null,
    )

    override fun commit(screen: PreferenceScreenPreference) {
        // No-op: Google Photos does not have a dedicated Morphe settings screen yet.
    }
}

private fun gmsCoreSupportResourcePatch() =
    app.morphe.patches.shared.misc.gms.gmsCoreSupportResourcePatch(
        fromPackageName = PHOTOS_PACKAGE_NAME,
        toPackageName = MORPHE_PHOTOS_PACKAGE_NAME,
        spoofedPackageSignature = "24bb24c05e47e0aefa68a58a766179d9b613a600",
        screen = DummyPreferenceScreen.SCREEN,
    ) {
        finalize {
            if (PackageNameConfig.isPackageNameChangeEnabled) {
                val targetPackageName = PackageNameConfig.effectivePackageName.ifEmpty { MORPHE_PHOTOS_PACKAGE_NAME }

                document("AndroidManifest.xml").use { document ->
                    val manifest = document.getNode("manifest") as Element
                    val originalPackageName = manifest.getAttribute("package")

                    manifest.setAttribute("package", targetPackageName)

                    val permissions = manifest.getElementsByTagName("permission").asSequence()
                    val usesPermissions = manifest.getElementsByTagName("uses-permission").asSequence()
                    val receiverNotExported = "DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"

                    (permissions + usesPermissions)
                        .map { it as Element }
                        .filter { it.getAttribute("android:name") == "$originalPackageName.$receiverNotExported" }
                        .forEach { it.setAttribute("android:name", "$targetPackageName.$receiverNotExported") }

                    val providers = manifest.getElementsByTagName("provider").asSequence()
                    for (node in providers) {
                        val provider = node as Element
                        val authorities = provider.getAttribute("android:authorities")
                        if (!authorities.startsWith("$originalPackageName.")) continue
                        provider.setAttribute("android:authorities", authorities.replace(originalPackageName, targetPackageName))
                    }
                }
            }
        }
    }
