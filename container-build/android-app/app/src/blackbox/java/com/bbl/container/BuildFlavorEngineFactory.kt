package com.bbl.container

import android.content.Context
import java.io.File
import top.niunaijun.blackbox.BlackBoxCore
import top.niunaijun.blackbox.app.configuration.ClientConfiguration

object BuildFlavorEngineFactory {
    fun create(): VirtualEngine = BlackBoxVirtualEngine()
}

class BlackBoxVirtualEngine : VirtualEngine {
    private val userId = 0
    private var attached = false
    private var created = false

    override fun attach(context: Context) {
        if (attached) return
        BlackBoxCore.get().doAttachBaseContext(context, object : ClientConfiguration() {
            override fun getHostPackageName(): String = context.packageName
            override fun isHideRoot(): Boolean = false
            override fun isUseVpnNetwork(): Boolean = false
            override fun isDisableFlagSecure(): Boolean = false
            override fun getLogSenderChatId(): String = ""
        })
        attached = true
    }

    override fun init(context: Context) {
        if (!attached) attach(context)
        if (!created) {
            BlackBoxCore.get().doCreate()
            created = true
        }
    }

    override fun status() = EngineStatus(
        "BLACKBOX",
        attached && created,
        if (attached && created) "Motor carregado; usuário virtual 0 pronto." else "Motor ainda não inicializado."
    )

    override fun isInstalled(packageName: String): Boolean =
        packageName.isNotBlank() && BlackBoxCore.get().isInstalled(packageName, userId)

    override fun installVirtual(apk: File, packageName: String): Result<Unit> = runCatching {
        require(apk.isFile && apk.length() > 0) { "APK inexistente ou vazio" }
        require(packageName.isNotBlank()) { "Package name vazio" }
        if (isInstalled(packageName)) return@runCatching
        val result = BlackBoxCore.get().installPackageAsUser(apk, userId)
        check(result.success) { "Falha ao instalar no contêiner: ${result.msg ?: "erro desconhecido"}" }
        check(result.packageName.isNullOrBlank() || result.packageName == packageName) {
            "Pacote instalado (${result.packageName}) difere do catálogo ($packageName)"
        }
    }

    override fun launchVirtual(packageName: String): Result<Unit> = runCatching {
        require(packageName.isNotBlank()) { "Package name vazio" }
        check(isInstalled(packageName)) { "Aplicativo não está instalado no contêiner" }
        check(BlackBoxCore.get().launchApk(packageName, userId)) { "O motor não conseguiu iniciar $packageName" }
    }

    override fun removeVirtual(packageName: String): Result<Unit> = runCatching {
        if (packageName.isNotBlank() && isInstalled(packageName)) {
            BlackBoxCore.get().uninstallPackageAsUser(packageName, userId)
        }
    }
}
