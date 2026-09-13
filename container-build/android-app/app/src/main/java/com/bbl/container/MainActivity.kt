package com.bbl.container

import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.util.Log
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.io.File
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    private val api by lazy { ApiClient(getString(R.string.server_url)) }
    private lateinit var list: RecyclerView
    private lateinit var status: TextView
    private lateinit var activate: Button
    private val appState by lazy { getSharedPreferences("virtual_app_state", 0) }

    @Volatile private var engineReady = false
    @Volatile private var engineError: String? = null

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        window.decorView.setBackgroundColor(Color.rgb(16, 18, 22))
        setContentView(R.layout.activity_main)

        list = findViewById(R.id.list)
        status = findViewById(R.id.status)
        activate = findViewById(R.id.activate)
        list.layoutManager = LinearLayoutManager(this)

        status.text = "Iniciando motor virtual..."
        activate.isEnabled = false

        val code = findViewById<EditText>(R.id.code)
        activate.setOnClickListener {
            if (!engineReady) {
                status.text = engineError ?: "Motor virtual ainda está iniciando..."
                return@setOnClickListener
            }
            thread {
                runCatching { api.activate(code.text.toString().trim()) }
                    .onSuccess {
                        getSharedPreferences("p", 0).edit().putString("token", it).apply()
                        runOnUiThread { load() }
                    }.onFailure { msg(it) }
            }
        }

        bootstrapEngine()
    }

    private fun bootstrapEngine() {
        thread(name = "bbl-blackbox-init") {
            val result = runCatching {
                val engine = VirtualEngineProvider.create()
                engine.init(applicationContext)
                val s = engine.status()
                check(s.available) { s.details }
                s
            }
            result.onSuccess { s ->
                engineReady = true
                runOnUiThread {
                    status.text = "Motor: ${s.name} — ${s.details}"
                    activate.isEnabled = true
                    if (getSharedPreferences("p", 0).contains("token")) load()
                }
            }.onFailure { e ->
                engineReady = false
                engineError = e.message ?: e.javaClass.simpleName
                Log.e("BBLContainer", "BlackBox init failed", e)
                runOnUiThread {
                    status.text = "Falha ao iniciar motor: ${engineError}"
                    activate.isEnabled = false
                }
            }
        }
    }

    private fun load() {
        val t = getSharedPreferences("p", 0).getString("token", "")!!
        runOnUiThread { status.text = "Sincronizando catálogo..." }
        thread {
            runCatching { api.catalog(t) }.onSuccess { apps ->
                cleanupRevoked(apps)
                runOnUiThread {
                    val e = runCatching { VirtualEngineProvider.create().status() }.getOrNull()
                    status.text = "${apps.size} app(s) liberado(s) • motor ${e?.name ?: "indisponível"}"
                    list.adapter = AppAdapter(apps) { a -> prepareAndRun(t, a) }
                }
            }.onFailure { msg(it) }
        }
    }

    private fun cleanupRevoked(current: List<CatalogApp>) {
        val allowedIds = current.map { it.id }.toSet()
        val engine = VirtualEngineProvider.create()
        val editor = appState.edit()
        appState.all.keys.filter { it.startsWith("pkg_") }.forEach { key ->
            val id = key.removePrefix("pkg_")
            if (id !in allowedIds) {
                val pkg = appState.getString(key, null)
                if (!pkg.isNullOrBlank() && runCatching { engine.status().available }.getOrDefault(false)) {
                    engine.removeVirtual(pkg)
                }
                File(filesDir, "virtual_apps/$id.apk").delete()
                editor.remove(key)
            }
        }
        editor.apply()
    }

    private fun prepareAndRun(t: String, a: CatalogApp) {
        val engine = VirtualEngineProvider.create()
        if (!engineReady || !runCatching { engine.status().available }.getOrDefault(false)) {
            status.text = engineError ?: "Motor virtual não está pronto."
            return
        }
        status.text = "Preparando ${a.name}..."
        thread {
            val f = File(filesDir, "virtual_apps/${a.id}.apk")
            f.parentFile?.mkdirs()
            runCatching {
                if (!f.exists() || !ApiClient.sha256(f).equals(a.sha256, ignoreCase = true)) {
                    api.download(t, a.downloadUrl, f)
                }
                require(ApiClient.sha256(f).equals(a.sha256, ignoreCase = true)) { "SHA-256 divergente" }
                val parsedPkg = packageManager.getPackageArchiveInfo(f.absolutePath, PackageManager.GET_META_DATA)?.packageName
                require(parsedPkg == a.packageName) {
                    "APK recebido pertence a ${parsedPkg ?: "pacote desconhecido"}, esperado ${a.packageName}"
                }
                engine.installVirtual(f, a.packageName).getOrThrow()
                appState.edit().putString("pkg_${a.id}", a.packageName).apply()
                engine.launchVirtual(a.packageName).getOrThrow()
            }.onSuccess {
                runOnUiThread { status.text = "Executando ${a.name}" }
            }.onFailure { msg(it) }
        }
    }

    private fun msg(e: Throwable) = runOnUiThread {
        Log.e("BBLContainer", "Operation failed", e)
        status.text = e.message ?: "Erro"
    }
}

class AppAdapter(private val items: List<CatalogApp>, private val click: (CatalogApp) -> Unit) : RecyclerView.Adapter<AppVH>() {
    override fun onCreateViewHolder(p: android.view.ViewGroup, v: Int) = AppVH(TextView(p.context).apply {
        setPadding(24, 24, 24, 24)
        textSize = 22f
        setTextColor(Color.WHITE)
        isFocusable = true
        isFocusableInTouchMode = true
        setBackgroundColor(Color.rgb(28, 31, 38))
    })
    override fun getItemCount() = items.size
    override fun onBindViewHolder(h: AppVH, i: Int) {
        val a = items[i]
        h.t.text = "${a.name}\n${a.packageName} • ${a.version}"
        h.t.setOnClickListener { click(a) }
    }
}
class AppVH(val t: TextView) : RecyclerView.ViewHolder(t)
