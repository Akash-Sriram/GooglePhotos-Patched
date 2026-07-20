package app.morphe.patches.googlephotos.misc.backup

import app.morphe.patcher.Fingerprint
import app.morphe.util.getReference
import com.android.tools.smali.dexlib2.iface.ClassDef
import com.android.tools.smali.dexlib2.iface.Method
import com.android.tools.smali.dexlib2.iface.instruction.NarrowLiteralInstruction
import com.android.tools.smali.dexlib2.iface.reference.StringReference

private fun Method.referencesString(value: String) =
    implementation?.instructions?.any {
        it.getReference<StringReference>()?.string == value
    } == true

private fun Method.referencesStringContaining(value: String) =
    implementation?.instructions?.any {
        it.getReference<StringReference>()?.string?.contains(value) == true
    } == true

internal object InCameraFolderSetterFingerprint : Fingerprint(
    returnType = "V",
    parameters = listOf("Z"),
    custom = { method, classDef ->
        classDef.methods.any { it.referencesString("Missing required properties:") } &&
        classDef.methods.any { it.referencesStringContaining(" inCameraFolder") } &&
        method.implementation?.instructions?.any {
            it is NarrowLiteralInstruction && it.narrowLiteral == 32
        } == true
    }
)

