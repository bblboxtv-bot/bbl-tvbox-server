package com.bbl.boxtv.launcher

import android.app.Activity
import android.app.AlertDialog
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.drawable.BitmapDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.widget.*
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

class V21Activity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val prefs by lazy { getSharedPreferences("bbl", Context.MODE_PRIVATE) }
    private lateinit var root: LinearLayout
    private lateinit var header: LinearLayout
    private lateinit var status: TextView
    private lateinit var clock: TextView
    private lateinit var logo: ImageView
    private lateinit var deviceId: String
    private var apps: List<RemoteApp> = emptyList()
    private var busy = false
    private var lastWallpaper = ""
    private var lastLogo = ""
    private var lastMessage = ""

    private val tick = object : Runnable {
        override fun run() {
            if (::clock.isInitialized) clock.text = SimpleDateFormat("dd/MM/yyyy  HH:mm", Locale("pt", "BR")).format(Date())
            handler.postDelayed(this, 30000)
        }
    }
    private val periodic = object : Runnable {
        override fun run() {
            if (token().isNotBlank()) sync()
            handler.postDelayed(this, 60000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        deviceId = DeviceIdentity.get(this)
        buildBase()
        tick.run()
        if (token().isBlank()) activation() else sync()
    }

    override fun onResume() {
        super.onResume()
        busy = false
        handler.removeCallbacks(periodic)
        if (::deviceId.isInitialized && token().isNotBlank()) sync()
        handler.postDelayed(periodic, 60000)
    }

    override fun onPause() {
        handler.removeCallbacks(periodic)
        super.onPause()
    }

    override fun onDestroy() {
        handler.removeCallbacks(periodic)
        handler.removeCallbacks(tick)
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun buildBase() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 18, 28, 18)
            setBackgroundColor(Color.rgb(8, 9, 12))
        }
        header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        logo = ImageView(this).apply { setImageResource(R.drawable.ic_bbl); scaleType = ImageView.ScaleType.FIT_CENTER }
        header.addView(logo, LinearLayout.LayoutParams(130, 72))
        val name = TextView(this).apply {
            text = "BBL.BOXTV"; textSize = 27f; setTextColor(Color.WHITE); setTypeface(typeface, 1); setPadding(12,0,0,0)
        }
        header.addView(name, LinearLayout.LayoutParams(0, -2, 1f))
        clock = TextView(this).apply { textSize = 18f; setTextColor(Color.WHITE); gravity = Gravity.END }
        header.addView(clock, LinearLayout.LayoutParams(300, -2))
        status = TextView(this).apply { textSize = 14f; setTextColor(Color.WHITE); setPadding(0, 4, 0, 10) }
        root.addView(header)
        root.addView(status)
        setContentView(root)
    }

    private fun clearBody() { while (root.childCount > 2) root.removeViewAt(2) }
    private fun token() = prefs.getString("device_token", "") ?: ""

    private fun activation(error: String = "") {
        clearBody()
        status.text = "ID: $deviceId"
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(90, 60, 90, 60) }
        box.addView(TextView(this).apply { text = "ATIVAÇÃO BBL.BOXTV"; textSize = 30f; setTextColor(Color.WHITE); gravity = Gravity.CENTER; setTypeface(typeface, 1) })
        box.addView(TextView(this).apply { text = if (error.isBlank()) "Digite o código gerado no painel" else error; textSize = 18f; setTextColor(if(error.isBlank()) Color.LTGRAY else Color.rgb(255,120,120)); gravity = Gravity.CENTER; setPadding(0,10,0,18) })
        val input = EditText(this).apply { hint = "BBL-XXXX"; textSize = 24f; isSingleLine = true; gravity = Gravity.CENTER; setTextColor(Color.WHITE); setHintTextColor(Color.GRAY) }
        val btn = Button(this).apply { text = "ATIVAR"; textSize = 20f; isAllCaps = false; setOnClickListener { doActivate(input.text.toString(), this) } }
        box.addView(input, LinearLayout.LayoutParams(-1,-2))
        box.addView(btn, LinearLayout.LayoutParams(-1,-2).apply { topMargin = 16 })
        root.addView(box, LinearLayout.LayoutParams(-1,-1))
        input.requestFocus()
    }

    private fun doActivate(code: String, btn: Button) {
        if (code.trim().isBlank()) return
        btn.isEnabled = false
        status.text = "Ativando... • ID: $deviceId"
        executor.execute {
            try {
                val t = ApiClient.enroll(deviceId, code)
                prefs.edit().putString("device_token", t).apply()
                val cfg = ApiClient.getPolicy(deviceId, t)
                runOnUiThread { render(cfg); Toast.makeText(this, "TV Box ativada", Toast.LENGTH_SHORT).show() }
            } catch (e: Exception) {
                runOnUiThread { activation("Código inválido ou servidor indisponível") }
            }
        }
    }

    private fun sync() {
        val t = token()
        if (t.isBlank()) { activation(); return }
        executor.execute {
            try {
                val cfg = ApiClient.getPolicy(deviceId, t)
                processCommands(t)
                runOnUiThread { render(cfg) }
            } catch (e: ApiClient.HttpStatusException) {
                runOnUiThread {
                    if (e.code == 401) { prefs.edit().remove("device_token").apply(); activation("Ativação necessária") }
                    else status.text = "Falha de sincronização • ID: $deviceId"
                }
            } catch (_: Exception) {
                runOnUiThread { status.text = "Servidor indisponível • ID: $deviceId" }
            }
        }
    }

    private fun render(cfg: DeviceConfig) {
        apps = cfg.apps
        clearBody()
        applyBrand(cfg)
        status.text = if (cfg.active) "ATIVO${if(cfg.expiresAt.isNotBlank()) " • validade: ${cfg.expiresAt.take(10)}" else ""} • ID: $deviceId" else "ACESSO BLOQUEADO • ID: $deviceId"
        if (!cfg.active) {
            root.addView(TextView(this).apply { text = "Acesso bloqueado ou validade encerrada.\nEntre em contato com seu revendedor."; textSize = 28f; setTextColor(Color.WHITE); gravity = Gravity.CENTER; setBackgroundColor(Color.argb(170,0,0,0)) }, LinearLayout.LayoutParams(-1,-1))
            return
        }
        if (cfg.message.isNotBlank() && cfg.message != lastMessage) {
            lastMessage = cfg.message
            AlertDialog.Builder(this).setTitle(cfg.brandingName).setMessage(cfg.message).setPositiveButton("OK", null).show()
        }

        val hero = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        hero.addView(bannerView(cfg.banners.firstOrNull(), cfg.brandingName), LinearLayout.LayoutParams(0, 330, 1.55f).apply { rightMargin = 12 })

        val featured = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        cfg.apps.take(2).forEach { featured.addView(appCard(it, true), LinearLayout.LayoutParams(0, 330, 1f).apply { setMargins(6,0,6,0) }) }
        if (cfg.apps.isEmpty()) featured.addView(TextView(this).apply { text="Sem aplicativos"; textSize=22f; setTextColor(Color.WHITE); gravity=Gravity.CENTER }, LinearLayout.LayoutParams(-1,-1))
        hero.addView(featured, LinearLayout.LayoutParams(0, 330, 1f))
        root.addView(hero, LinearLayout.LayoutParams(-1, 330).apply { bottomMargin = 10 })

        val scroll = HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; isFillViewport = true }
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        cfg.apps.forEach { row.addView(appCard(it, false), LinearLayout.LayoutParams(245, 180).apply { setMargins(6,2,6,2) }) }
        scroll.addView(row)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        if (row.childCount > 0) row.getChildAt(0).requestFocus()
        maybeAutoInstall(cfg.apps)
    }

    private fun bannerView(b: RemoteBanner?, brand: String): FrameLayout {
        val frame = FrameLayout(this).apply { setBackgroundColor(Color.argb(95,0,0,0)) }
        if (b == null || b.url.isBlank()) {
            frame.addView(TextView(this).apply { text = brand; textSize = 36f; setTextColor(Color.WHITE); gravity = Gravity.CENTER; setTypeface(typeface,1) }, FrameLayout.LayoutParams(-1,-1))
            return frame
        }
        if (b.type.equals("video", true)) {
            val v = VideoView(this).apply { setVideoURI(Uri.parse(ApiClient.absoluteUrl(b.url))); setOnPreparedListener { it.isLooping = true; start() } }
            frame.addView(v, FrameLayout.LayoutParams(-1,-1))
        } else {
            val img = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP }
            frame.addView(img, FrameLayout.LayoutParams(-1,-1))
            executor.execute { try { val bytes = ApiClient.downloadBytes(b.url); val bmp = BitmapFactory.decodeByteArray(bytes,0,bytes.size); runOnUiThread { if (bmp != null) img.setImageBitmap(bmp) } } catch (_: Exception) {} }
        }
        return frame
    }

    private fun appCard(app: RemoteApp, featured: Boolean): FrameLayout {
        val installedCode = installedVersion(app.packageName)
        val installed = installedCode != null
        val needsUpdate = installed && app.versionCode > 0 && installedCode!! < app.versionCode
        val caption = when { needsUpdate -> "${app.label}\nATUALIZAR"; installed -> app.label; else -> "${app.label}\nINSTALAR" }
        val card = FrameLayout(this).apply {
            isFocusable = true; isClickable = true; setPadding(10,10,10,8); setBackgroundColor(Color.argb(120,55,55,55))
            setOnClickListener { if (installed && !needsUpdate) launchApp(app.packageName) else install(app, true) }
            setOnFocusChangeListener { v, focused ->
                v.setBackgroundColor(if(focused) Color.argb(190,200,200,200) else Color.argb(120,55,55,55))
                v.animate().scaleX(if(focused) 1.08f else 1f).scaleY(if(focused) 1.08f else 1f).setDuration(120).start()
            }
        }
        val icon = ImageView(this).apply {
            scaleType = ImageView.ScaleType.FIT_CENTER
            try { setImageDrawable(packageManager.getApplicationIcon(app.packageName)) } catch (_: Exception) { setImageResource(R.drawable.ic_bbl) }
        }
        val size = if (featured) 185 else 100
        card.addView(icon, FrameLayout.LayoutParams(size,size,Gravity.TOP or Gravity.CENTER_HORIZONTAL).apply { topMargin = if(featured) 34 else 16 })
        card.addView(TextView(this).apply { text=caption; textSize=if(featured)22f else 18f; setTextColor(Color.WHITE); gravity=Gravity.CENTER; maxLines=2 }, FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM).apply { setMargins(6,0,6,8) })
        return card
    }

    private fun applyBrand(cfg: DeviceConfig) {
        if (cfg.wallpaperUrl != lastWallpaper) {
            lastWallpaper = cfg.wallpaperUrl
            if (cfg.wallpaperUrl.isBlank()) root.setBackgroundColor(Color.rgb(8,9,12))
            else executor.execute { try { val bytes=ApiClient.downloadBytes(cfg.wallpaperUrl); val bmp=BitmapFactory.decodeByteArray(bytes,0,bytes.size); runOnUiThread { if(bmp!=null) root.background=BitmapDrawable(resources,bmp) } } catch (_: Exception) {} }
        }
        if (cfg.logoUrl != lastLogo) {
            lastLogo = cfg.logoUrl
            if (cfg.logoUrl.isBlank()) logo.setImageResource(R.drawable.ic_bbl)
            else executor.execute { try { val bytes=ApiClient.downloadBytes(cfg.logoUrl); val bmp=BitmapFactory.decodeByteArray(bytes,0,bytes.size); runOnUiThread { if(bmp!=null) logo.setImageBitmap(bmp) } } catch (_: Exception) {} }
        }
    }

    private fun installedVersion(pkg: String): Long? = try {
        val i = packageManager.getPackageInfo(pkg, 0)
        if (Build.VERSION.SDK_INT >= 28) i.longVersionCode else @Suppress("DEPRECATION") i.versionCode.toLong()
    } catch (_: Exception) { null }

    private fun maybeAutoInstall(list: List<RemoteApp>) {
        if (busy) return
        val a = list.firstOrNull { val v=installedVersion(it.packageName); (v == null || (it.versionCode > 0 && v < it.versionCode)) && it.downloadUrl.isNotBlank() } ?: return
        val key = "${a.packageName}:${a.versionCode}:${a.sha256}"
        if (prefs.getString("last_auto_install_key", "") == key) return
        prefs.edit().putString("last_auto_install_key", key).apply()
        install(a, false)
    }

    private fun install(app: RemoteApp, manual: Boolean) {
        if (busy || app.downloadUrl.isBlank()) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
            Toast.makeText(this, "Autorize BBL.BOXTV a instalar aplicativos", Toast.LENGTH_LONG).show()
            try { startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName"))) } catch (_: Exception) { startActivity(Intent(Settings.ACTION_SECURITY_SETTINGS)) }
            return
        }
        busy = true
        executor.execute {
            val apk = File(cacheDir, "remote_apks/${app.packageName}-${app.versionCode}.apk")
            try {
                ApiClient.downloadApk(app, apk)
                val installer = packageManager.packageInstaller
                val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply { setAppPackageName(app.packageName) }
                val id = installer.createSession(params)
                installer.openSession(id).use { session ->
                    apk.inputStream().use { input -> session.openWrite("base.apk", 0, apk.length()).use { out -> input.copyTo(out); session.fsync(out) } }
                    val callback = Intent(this, InstallResultReceiver::class.java).apply { putExtra("package_name", app.packageName); putExtra("app_label", app.label) }
                    val flags = PendingIntent.FLAG_UPDATE_CURRENT or if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
                    session.commit(PendingIntent.getBroadcast(this, id, callback, flags).intentSender)
                }
            } catch (e: Exception) {
                busy = false
                runOnUiThread { Toast.makeText(this, if(manual) "Falha ao instalar: ${e.message}" else "Falha na instalação automática", Toast.LENGTH_LONG).show() }
            }
        }
    }

    private fun launchApp(pkg: String) {
        packageManager.getLaunchIntentForPackage(pkg)?.let { startActivity(it) }
            ?: apps.firstOrNull { it.packageName == pkg }?.let { install(it, true) }
    }

    private fun processCommands(t: String) {
        try {
            ApiClient.getCommands(deviceId, t).forEach { cmd ->
                var result = "ok"
                try {
                    when (cmd.command.uppercase()) {
                        "SYNC", "RELOAD" -> result = "sincronizado"
                        "CLEAR_CACHE" -> { cacheDir.deleteRecursively(); cacheDir.mkdirs(); result = "cache limpo" }
                        "OPEN_SETTINGS" -> { runOnUiThread { startActivity(Intent(Settings.ACTION_SETTINGS)) }; result = "configurações abertas" }
                        else -> result = "comando recebido"
                    }
                    ApiClient.sendCommandResult(deviceId, t, cmd.id, "done", result)
                } catch (e: Exception) { ApiClient.sendCommandResult(deviceId, t, cmd.id, "error", e.message ?: "erro") }
            }
        } catch (_: Exception) {}
    }
}
