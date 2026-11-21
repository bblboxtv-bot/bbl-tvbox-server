package com.bbl.boxtv.launcher

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import java.io.File

@Suppress("DEPRECATION")
internal fun uploadBblConfig(activity: Activity, deviceId: String, token: String, commandId: String) {
    val storageAllowed = when {
        Build.VERSION.SDK_INT >= 30 -> Environment.isExternalStorageManager()
        Build.VERSION.SDK_INT >= 23 ->
            activity.checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
        else -> true
    }
    if (!storageAllowed) {
        activity.runOnUiThread {
            if (!activity.isFinishing && !activity.isDestroyed) {
                AlertDialog.Builder(activity)
                    .setTitle("Extrair config")
                    .setMessage("Autorize a leitura do Android/.config e solicite a extração novamente.")
                    .setNegativeButton("Agora não", null)
                    .setPositiveButton("Autorizar") { _, _ ->
                        if (Build.VERSION.SDK_INT >= 30) {
                            runCatching {
                                activity.startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                    Uri.parse("package:${activity.packageName}")))
                            }
                        } else if (Build.VERSION.SDK_INT >= 23) {
                            activity.requestPermissions(arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE), 320)
                        }
                    }.show()
            }
        }
        ApiClient.reportCommand(deviceId, token, commandId, "error", "Aguardando permissão de armazenamento")
        return
    }

    val file = File(Environment.getExternalStorageDirectory(), "Android/.config")
    val maxSize = 1024 * 1024
    val size = file.length()
    if (size !in 1L..maxSize.toLong()) {
        ApiClient.reportCommand(deviceId, token, commandId, "error", "Arquivo .config ausente, vazio ou maior que 1 MB")
        return
    }
    val data = ByteArray(size.toInt())
    try {
        java.io.DataInputStream(file.inputStream()).use { input ->
            input.readFully(data)
            check(input.read() == -1)
        }
    } catch (_: Exception) {
        ApiClient.reportCommand(deviceId, token, commandId, "error", "Falha ao ler o .config")
        return
    }

    ApiClient.uploadConfigExport(deviceId, token, commandId, data)
}
