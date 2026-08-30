package app.morphe.patches.googlephotos.misc.updater

import app.morphe.patcher.Fingerprint

object HomeActivityOnCreateFingerprint : Fingerprint(
    definingClass = "Lcom/google/android/apps/photos/home/HomeActivity;",
    name = "onCreate",
    returnType = "V",
    parameters = listOf("Landroid/os/Bundle;"),
)
