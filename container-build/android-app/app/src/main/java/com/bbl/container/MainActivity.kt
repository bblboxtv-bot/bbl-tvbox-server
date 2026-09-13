package com.bbl.container

import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.io.File
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    private val api by lazy { ApiClient(getString(R.string.server_url)) }
    private lateinit var status: TextView
    private lateinit var list: RecyclerView
    private lateinit var login: Button
    @Volatile private var engineReady = false

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.decorView.setBackgroundColor(Color.rgb(16,18,22))
        setContentView(R.layout.activity_main)
        status=findViewById(R.id.status)
        list=findViewById(R.id.list)
        login=findViewById(R.id.login)
        list.layoutManager=LinearLayoutManager(this)
        val user=findViewById<EditText>(R.id.username)
        val pass=findViewById<EditText>(R.id.password)

        login.setOnClickListener {
            val u=user.text.toString().trim()
            val p=pass.text.toString()
            if(u.isBlank() || p.isBlank()) { status.text="Informe usuário e senha."; return@setOnClickListener }
            if(!engineReady) { status.text="Motor virtual ainda está iniciando..."; return@setOnClickListener }
            status.text="Entrando..."
            login.isEnabled=false
            thread {
                runCatching { api.login(u,p,deviceId()) }
                    .onSuccess { s -> runOnUiThread { login.isEnabled=true; status.text="Login realizado. Buscando aplicativos..."; loadCatalog(s.token) } }
                    .onFailure { e -> runOnUiThread { login.isEnabled=true; status.text=e.message ?: "Login recusado pelo servidor" } }
            }
        }

        thread {
            runCatching { VirtualEngineProvider.create().init(applicationContext); VirtualEngineProvider.create().status() }
                .onSuccess { s -> engineReady=s.available; runOnUiThread { status.text=if(s.available) "Entre com o usuário e a senha criados no painel Base 2." else s.details } }
                .onFailure { e -> runOnUiThread { status.text="Falha ao iniciar motor: ${e.message}" } }
        }
    }

    private fun deviceId(): String = Settings.Secure.getString(contentResolver,Settings.Secure.ANDROID_ID) ?: android.os.Build.MODEL

    private fun loadCatalog(token:String) {
        thread {
            runCatching { api.catalog(token) }
                .onSuccess { apps -> runOnUiThread {
                    status.text=if(apps.isEmpty()) "Libere um aplicativo para este cliente no painel Base 2." else "Aplicativos liberados: ${apps.size}"
                    list.adapter=AppAdapter(apps) { app -> runApp(token,app) }
                }}
                .onFailure { e -> runOnUiThread { status.text=e.message ?: "Falha ao consultar aplicativos" } }
        }
    }

    private fun runApp(token:String, app:CatalogApp) {
        status.text="Preparando ${app.name}..."
        thread {
            val apk=File(filesDir,"virtual_apps/${app.id}.apk")
            apk.parentFile?.mkdirs()
            runCatching {
                if(!apk.exists() || (app.sha256.isNotBlank() && !ApiClient.sha256(apk).equals(app.sha256,true))) api.download(token,app.downloadUrl,apk)
                if(app.sha256.isNotBlank()) require(ApiClient.sha256(apk).equals(app.sha256,true)) { "Arquivo baixado não passou na verificação SHA-256" }
                val pkg=packageManager.getPackageArchiveInfo(apk.absolutePath,PackageManager.GET_META_DATA)?.packageName
                require(pkg==app.packageName) { "APK recebido não corresponde ao pacote liberado" }
                val engine=VirtualEngineProvider.create()
                engine.installVirtual(apk,app.packageName).getOrThrow()
                engine.launchVirtual(app.packageName).getOrThrow()
            }.onSuccess { runOnUiThread { status.text="Executando ${app.name}" } }
             .onFailure { e -> runOnUiThread { status.text=e.message ?: "Erro" } }
        }
    }
}

class AppAdapter(private val items:List<CatalogApp>, private val click:(CatalogApp)->Unit):RecyclerView.Adapter<AppVH>() {
    override fun onCreateViewHolder(parent:android.view.ViewGroup,viewType:Int)=AppVH(TextView(parent.context).apply { setPadding(24,24,24,24); textSize=22f; setTextColor(Color.WHITE); isFocusable=true; setBackgroundColor(Color.rgb(28,31,38)) })
    override fun getItemCount()=items.size
    override fun onBindViewHolder(holder:AppVH,position:Int) { val a=items[position]; holder.text.text="${a.name}\n${a.packageName} • ${a.version}"; holder.text.setOnClickListener { click(a) } }
}
class AppVH(val text:TextView):RecyclerView.ViewHolder(text)
