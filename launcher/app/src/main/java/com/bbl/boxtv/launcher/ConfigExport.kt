package com.bbl.boxtv.launcher

import android.content.Context
import java.io.File

internal fun uploadBblConfig(context: Context, deviceId: String, token: String, commandId: String) {
    val base = context.getExternalFilesDir(null) ?: context.filesDir
    val file = File(base, "BBLBOX/.config")
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
