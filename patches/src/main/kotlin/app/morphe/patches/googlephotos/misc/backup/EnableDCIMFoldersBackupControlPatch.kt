package app.morphe.patches.googlephotos.misc.backup

import app.morphe.patches.shared.compat.AppCompatibilities
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.util.cloneMutable
import app.morphe.util.getReference
import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import com.android.tools.smali.dexlib2.Opcode
import com.android.tools.smali.dexlib2.AccessFlags
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
                        val fieldRef = instr.getReference<FieldReference>()!!
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
            add("iget-object v$N, p0, ${classDef.type}->$filepathFieldName:$filepathFieldType")
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

        // 2. Patch the legacy DCIM check method
        val legacyMethod = LegacyDCIMCheckFingerprint.methodOrNull
        if (legacyMethod != null) {
            val legacyClassDef = mutableClassDefBy(legacyMethod.definingClass)

            val isStatic = AccessFlags.STATIC.isSet(legacyMethod.accessFlags)
            val pathRegister = if (isStatic) "p0" else "p1"

            val legacyN = legacyMethod.implementation!!.registerCount
            val legacyPatchInstructions = buildList {
                add("if-eqz $pathRegister, :cond_skip")
                add("move-object v$legacyN, $pathRegister")
                add("sget-object v${legacyN+1}, Ljava/util/Locale;->US:Ljava/util/Locale;")
                add("invoke-virtual {v$legacyN, v${legacyN+1}}, Ljava/lang/String;->toLowerCase(Ljava/util/Locale;)Ljava/lang/String;")
                add("move-result-object v$legacyN")
                add("const-string v${legacyN+1}, \"/dcim/camera/\"")
                add("invoke-virtual {v$legacyN, v${legacyN+1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z")
                add("move-result v${legacyN+1}")
                add("if-eqz v${legacyN+1}, :cond_skip")
                add("const-string v${legacyN+1}, \"/dcim/camera\"")
                add("invoke-virtual {v$legacyN, v${legacyN+1}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z")
                add("move-result v$legacyN")
                add("if-eqz v$legacyN, :cond_skip")
                add("const/4 v$legacyN, 0")
                add("return v$legacyN")
                add(":cond_skip")
            }

            val clonedLegacyMethod = legacyMethod.cloneMutable(
                additionalRegisters = 4
            )

            clonedLegacyMethod.addInstructions(0, legacyPatchInstructions.joinToString("\n"))

            legacyClassDef.methods.apply {
                remove(legacyMethod)
                add(clonedLegacyMethod)
            }
        }
    }
}

