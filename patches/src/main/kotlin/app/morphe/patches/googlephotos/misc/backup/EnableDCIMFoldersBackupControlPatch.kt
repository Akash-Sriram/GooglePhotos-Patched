package app.morphe.patches.googlephotos.misc.backup

import app.morphe.patches.shared.compat.AppCompatibilities
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.util.cloneMutable
import app.morphe.util.getReference
import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import com.android.tools.smali.dexlib2.Opcode
import com.android.tools.smali.dexlib2.iface.instruction.formats.Instruction21c
import com.android.tools.smali.dexlib2.iface.reference.FieldReference
import com.android.tools.smali.dexlib2.iface.reference.StringReference
import app.morphe.patcher.patch.PatchException

@Suppress("unused")
val enableDCIMFoldersBackupControlPatch = bytecodePatch(
    name = "Enable DCIM folders backup control",
    description = "Disables always on backup for the Camera and other DCIM folders, allowing you to control backup " +
        "for each folder individually. This will make the app default to having no folders backed up.",
    default = false,
) {
    compatibleWith(AppCompatibilities.GOOGLE_PHOTOS)

    execute {
        val method = InCameraFolderSetterFingerprint.method
        val classDef = mutableClassDefBy(method.definingClass)

        // Find the filepath field name and descriptor type
        var filepathFieldName: String? = null
        var filepathFieldType: String? = null

        classDef.methods.forEach { m ->
            if (m.implementation?.instructions?.any {
                    it.getReference<StringReference>()?.string == "Null filepath"
                } == true) {
                m.implementation!!.instructions.forEach { instr ->
                    if (instr.opcode == Opcode.IPUT_OBJECT) {
                        val fieldRef = (instr as Instruction21c).reference as FieldReference
                        filepathFieldName = fieldRef.name
                        filepathFieldType = fieldRef.type
                    }
                }
            }
        }

        if (filepathFieldName == null || filepathFieldType == null) {
            throw PatchException("Could not find filepath field in builder class")
        }

        val N = method.implementation!!.registerCount
        val isOptional = filepathFieldType!!.contains("Optional")

        val patchInstructions = buildList {
            add("iget-object v$N, p0, L${classDef.type};->$filepathFieldName:$filepathFieldType")
            add("if-eqz v$N, :cond_skip")
            if (isOptional) {
                add("invoke-virtual {v$N}, $filepathFieldType->isPresent()Z")
                add("move-result v${N+1}")
                add("if-eqz v${N+1}, :cond_skip")
                add("invoke-virtual {v$N}, $filepathFieldType->get()Ljava/lang/Object;")
                add("move-result-object v$N")
            }
            add("check-cast v$N, Ljava/lang/String;")
            add("sget-object v${N+1}, Ljava/util/Locale;->US:Ljava/util/Locale;")
            add("invoke-virtual {v$N, v${N+1}}, Ljava/lang/String;->toLowerCase(Ljava/util/Locale;)Ljava/lang/String;")
            add("move-result-object v$N")
            add("const-string v${N+1}, \"/dcim/camera/\"")
            add("invoke-virtual {v$N, v${N+1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z")
            add("move-result v${N+1}")
            add("if-eqz v${N+1}, :cond_set_false")
            add("const-string v${N+1}, \"/dcim/camera\"")
            add("invoke-virtual {v$N, v${N+1}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z")
            add("move-result v$N")
            add("if-nez v$N, :cond_skip")
            add(":cond_set_false")
            add("const/4 p1, 0")
            add(":cond_skip")
        }

        val clonedMethod = method.cloneMutable(
            additionalRegisters = 5
        )

        clonedMethod.addInstructions(0, patchInstructions.joinToString("\n"))

        classDef.methods.apply {
            remove(method)
            add(clonedMethod)
        }
    }
}

