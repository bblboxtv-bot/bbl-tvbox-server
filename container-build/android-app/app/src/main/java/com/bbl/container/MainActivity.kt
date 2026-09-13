package com.bbl.container

import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.ViewGroup
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
    private lateinit var user: EditText
    private lateinit var pass: EditText
    @Volatile private var engineReady = false
    @Volatile private var loginRunning = false

    private val prefs by lazy { getSharedPreferences("base2_login", Context.MODE_PRIVATE) }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.decorView.setBackgroundColor(Color.rgb(16,18,22))
        setContentView(R.layout.activity_main)
        status=findViewById(R.id.status)
        list=findViewById(R.id.list)
        login=findViewById(R.id.login)
        user=findViewById(R.id.username)
        pass=findViewById(R.id.password)
        list.layoutManager=LinearLayoutManager(this)

        val savedUser=prefs.getString("username","") ?: ""
        val savedPass=prefs.getString("password","") ?: ""
        user.setText(savedUser)
        pass.setText(savedPass)
        if(savedUser.isBlank()) user.requestFocus() else login.requestFocus()

        login.setOnClickListener { performLogin(user.text.toString().trim(),pass.text.toString(),false) }

        thread {
            runCatching { VirtualEngineProvider.create().init(applicationContext); VirtualEngineProvider.create().status() }
                .onSuccess { s ->
                    engineReady=s.available
                    runOnUiThread {
                        if(!s.available) {
                            status.text=s.details
                        } else if(savedUser.isNotBlank() && savedPass.isNotBlank()) {
                            status.text="Entrando automaticamente..."
                            performLogin(savedUser,savedPass,true)
                        } else {
                            status.text="Digite USUÁRIO e SENHA e pressione ENTRAR."
                        }
                    }
                }
                .onFailure { e -> runOnUiThread { status.text="Falha ao iniciar motor: ${e.message}" } }
        }
    }

    private fun performLogin(u:String,p:String,automatic:Boolean) {
        if(loginRunning) return
        if(u.isBlank() || p.isBlank()) {
            status.text="Informe USUÁRIO e SENHA."
            if(u.isBlank()) user.requestFocus() else pass.requestFocus()
            return
        }
        if(!engineReady) {
            status.text="Motor virtual ainda está iniciando..."
            return
        }
        loginRunning=true
        status.text=if(automatic) "Entrando automaticamente..." else "Conectando ao Base 2..."
        login.isEnabled=false
        thread {
            runCatching { api.login(u,p,deviceId()) }
                .onSuccess { s ->
                    prefs.edit().putString("username",u).putString("password",p).apply()
                    runOnUiThread {
                        loginRunning=false
                        login.isEnabled=true
                        status.text="Login realizado. Buscando aplicativos..."
                        loadCatalog(s.token,s.deviceId)
                    }
                }
                .onFailure { e -> runOnUiThread {
                    loginRunning=false
                    login.isEnabled=true
                    status.text=when(e.message){
                        "invalid_credentials" -> "Usuário ou senha inválidos."
                        "blocked" -> "Cliente bloqueado no painel Base 2."
                        "expired" -> "Cliente vencido no painel Base 2."
                        "device_in_use" -> "Este usuário está vinculado a outro aparelho."
                        else -> e.message ?: "Falha ao conectar ao Base 2"
                    }
                    user.requestFocus()
                } }
        }
    }

    private fun deviceId(): String = Settings.Secure.getString(contentResolver,Settings.Secure.ANDROID_ID) ?: android.os.Build.MODEL

    private fun loadCatalog(token:String, deviceId:String) {
        thread {
            runCatching { api.catalog(token,deviceId) }
                .onSuccess { apps -> runOnUiThread {
                    status.text=if(apps.isEmpty()) "Nenhum aplicativo liberado para este cliente no painel Base 2." else "Aplicativos liberados: ${apps.size} — use as setas para escolher."
                    list.adapter=AppAdapter(apps) { app -> runApp(token,app) }
                    if(apps.isNotEmpty()) list.post { list.findViewHolderForAdapterPosition(0)?.itemView?.requestFocus() }
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
    private fun background(focused:Boolean):GradientDrawable = GradientDrawable().apply {
        cornerRadius=18f
        setColor(if(focused) Color.rgb(58,51,31) else Color.rgb(28,31,38))
        setStroke(if(focused) 5 else 2, if(focused) Color.rgb(245,196,81) else Color.rgb(82,87,98))
    }

    override fun onCreateViewHolder(parent:ViewGroup,viewType:Int):AppVH {
        val view=TextView(parent.context).apply {
            setPadding(30,26,30,26)
            textSize=22f
            setTextColor(Color.WHITE)
            gravity=Gravity.CENTER_VERTICAL
            minHeight=132
            isFocusable=true
            isFocusableInTouchMode=true
            isClickable=true
            background=background(false)
            layoutParams=RecyclerView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                setMargins(8,10,8,16)
            }
        }
        return AppVH(view)
    }

    override fun getItemCount()=items.size

    override fun onBindViewHolder(holder:AppVH,position:Int) {
        val a=items[position]
        holder.text.text="${a.name}\n${a.packageName}  •  ${a.version}\nPRESSIONE OK PARA ABRIR / INSTALAR"
        holder.text.background=background(false)
        holder.text.setOnFocusChangeListener { _, focused ->
            holder.text.background=background(focused)
            holder.text.setTextColor(if(focused) Color.rgb(255,233,164) else Color.WHITE)
            holder.text.scaleX=if(focused) 1.02f else 1f
            holder.text.scaleY=if(focused) 1.02f else 1f
        }
        holder.text.setOnClickListener { click(a) }
    }
}

class AppVH(val text:TextView):RecyclerView.ViewHolder(text)
