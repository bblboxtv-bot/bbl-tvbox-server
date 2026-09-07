package com.bbl.boxtv.launcher

import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.security.MessageDigest

internal data class RemoteApp(
    val packageName: String,
    val label: String,
    val category: String = "Aplicativos",
    val downloadUrl: String = "",
    val versionName: String = "",
    val versionCode: Long = 0L,
    val sha256: String = ""
)

internal data class RemoteBanner(
    val id: String,
    val name: String,
    val type: String,
    val url: String
)

internal data class RemoteCommand(
    val id: String,
    val command: String,
    val payload: String
)

internal data class DeviceConfig(
    val active: Boolean,
    val pending: Boolean = false,
    val expiresAt: String = "",
    val apps: List<RemoteApp> = emptyList(),
    val brandingName: String = "BBL.BOXTV",
    val logoUrl: String = "",
    val wallpaperUrl: String = "",
    val message: String = "",
    val banners: List<RemoteBanner> = emptyList()
)

internal object ApiClient {
    private val apiBaseUrl: String = BuildConfig.API_BASE_URL.trimEnd('/')

    fun absoluteUrl(value: String): String {
        val v = value.trim()
        if (v.startsWith("http://") || v.startsWith("https://")) return v
        return "$apiBaseUrl/${v.trimStart('/')}"
    }

    fun enroll(deviceId: String, activationCode: String): String {
        val conn = URL("$apiBaseUrl/api/enroll").openConnection() as HttpURLConnection
        try {
            conn.doOutput = true
            conn.connectTimeout = 10000
            conn.readTimeout = 10000
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Accept", "application/json")
            val body = JSONObject()
                .put("activationCode", activationCode.trim())
                .put("deviceId", deviceId)
                .put("manufacturer", android.os.Build.MANUFACTURER ?: "")
                .put("model", android.os.Build.MODEL ?: "")
                .put("android_version", android.os.Build.VERSION.RELEASE ?: "")
                .put("launcher_version", BuildConfig.VERSION_NAME)
                .toString()
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) throw HttpStatusException(code, text)
            val json = JSONObject(text)
            return json.optString("device_token", json.optString("deviceToken", json.optString("token"))).also {
                if (it.isBlank()) throw RuntimeException("Servidor não retornou token")
            }
        } finally { conn.disconnect() }
    }

    fun getPolicy(deviceId: String, token: String): DeviceConfig {
        val encodedId = URLEncoder.encode(deviceId, "UTF-8")
        val conn = URL("$apiBaseUrl/api/devices/$encodedId/policy").openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 10000
            conn.readTimeout = 10000
            conn.requestMethod = "GET"
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("Authorization", "Bearer $token")
            val code = conn.responseCode
            if (code !in 200..299) throw HttpStatusException(code)
            val json = JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
            val appsJson = json.optJSONArray("apps")
            val apps = mutableListOf<RemoteApp>()
            if (appsJson != null) for (i in 0 until appsJson.length()) {
                val app = appsJson.optJSONObject(i) ?: continue
                val pkg = app.optString("package_name").trim()
                if (pkg.isNotBlank()) {
                    apps += RemoteApp(
                        packageName = pkg,
                        label = app.optString("name", pkg).ifBlank { pkg },
                        category = app.optString("category", "Aplicativos").ifBlank { "Aplicativos" },
                        downloadUrl = app.optString("download_url", "").trim(),
                        versionName = app.optString("version_name", "").trim(),
                        versionCode = app.optString("version_code", "0").toLongOrNull() ?: app.optLong("version_code", 0L),
                        sha256 = app.optString("sha256", "").trim().lowercase()
                    )
                }
            }
            val branding = json.optJSONObject("brand") ?: json.optJSONObject("branding") ?: JSONObject()
            val locked = json.optBoolean("locked", false) || json.optBoolean("expired", false)
            return DeviceConfig(
                active = !locked,
                expiresAt = json.optString("expires_at", ""),
                apps = apps,
                brandingName = branding.optString("name", json.optString("branding_name", "BBL.BOXTV")),
                logoUrl = branding.optString("logo_url", json.optString("logo_url", "")),
                wallpaperUrl = branding.optString("wallpaper_url", json.optString("wallpaper_url", "")),
                message = json.optString("message", branding.optString("message", "")),
                banners = buildList {
                    val arr = json.optJSONArray("banners")
                    if (arr != null) for (i in 0 until arr.length()) {
                        val b = arr.optJSONObject(i) ?: continue
                        add(RemoteBanner(
                            id = b.optString("id", i.toString()),
                            name = b.optString("name", "Banner"),
                            type = b.optString("type", "image"),
                            url = b.optString("url", "")
                        ))
                    }
                }
            )
        } finally { conn.disconnect() }
    }

    fun downloadBytes(urlValue: String): ByteArray {
        if (urlValue.isBlank()) return ByteArray(0)
        val conn = URL(absoluteUrl(urlValue)).openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 10000
            conn.readTimeout = 20000
            conn.instanceFollowRedirects = true
            conn.requestMethod = "GET"
            if (conn.responseCode !in 200..299) throw HttpStatusException(conn.responseCode)
            return conn.inputStream.use { it.readBytes() }
        } finally { conn.disconnect() }
    }

    fun downloadApk(app: RemoteApp, destination: File) {
        if (app.downloadUrl.isBlank()) throw RuntimeException("Aplicativo sem URL de download")
        val conn = URL(absoluteUrl(app.downloadUrl)).openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 15000
            conn.readTimeout = 60000
            conn.instanceFollowRedirects = true
            conn.requestMethod = "GET"
            conn.setRequestProperty("Accept", "application/vnd.android.package-archive,application/octet-stream,*/*")
            val code = conn.responseCode
            if (code !in 200..299) throw HttpStatusException(code)
            destination.parentFile?.mkdirs()
            conn.inputStream.use { input -> destination.outputStream().use { output -> input.copyTo(output) } }
            if (destination.length() <= 0L) throw RuntimeException("APK vazio")
            if (app.sha256.isNotBlank()) {
                val md = MessageDigest.getInstance("SHA-256")
                destination.inputStream().use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val n = input.read(buffer)
                        if (n <= 0) break
                        md.update(buffer, 0, n)
                    }
                }
                val got = md.digest().joinToString("") { "%02x".format(it) }
                if (!got.equals(app.sha256, ignoreCase = true)) {
                    destination.delete()
                    throw RuntimeException("Falha na verificação do APK")
                }
            }
        } finally { conn.disconnect() }
    }

    internal class HttpStatusException(val code: Int, val body: String = "") : RuntimeException("HTTP $code $body")

    fun getCommands(deviceId: String, token: String): List<RemoteCommand> {
        val encodedId = URLEncoder.encode(deviceId, "UTF-8")
        val conn = URL("$apiBaseUrl/api/devices/$encodedId/commands").openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 10000
            conn.readTimeout = 10000
            conn.requestMethod = "GET"
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("Authorization", "Bearer $token")
            val code = conn.responseCode
            if (code !in 200..299) throw HttpStatusException(code)
            val arr = org.json.JSONArray(conn.inputStream.bufferedReader().use { it.readText() })
            val out = mutableListOf<RemoteCommand>()
            for (i in 0 until arr.length()) {
                val x = arr.optJSONObject(i) ?: continue
                out += RemoteCommand(x.optString("id"), x.optString("command"), x.opt("payload")?.toString() ?: "{}")
            }
            return out
        } finally { conn.disconnect() }
    }

    fun reportCommand(deviceId: String, token: String, commandId: String, status: String, result: String) {
        val encodedId = URLEncoder.encode(deviceId, "UTF-8")
        val encodedCmd = URLEncoder.encode(commandId, "UTF-8")
        val conn = URL("$apiBaseUrl/api/devices/$encodedId/commands/$encodedCmd/result").openConnection() as HttpURLConnection
        try {
            conn.doOutput = true
            conn.connectTimeout = 10000
            conn.readTimeout = 10000
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Authorization", "Bearer $token")
            val body = JSONObject().put("status", status).put("result", result).toString()
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            conn.responseCode
        } finally { conn.disconnect() }
    }
}
