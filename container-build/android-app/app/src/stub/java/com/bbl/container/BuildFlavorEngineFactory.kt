package com.bbl.container

import android.content.Context
import java.io.File

object BuildFlavorEngineFactory {
    fun create(): VirtualEngine = StubVirtualEngine()
}

class StubVirtualEngine : VirtualEngine {
    override fun init(context: Context) = Unit
    override fun status() = EngineStatus("SEM MOTOR", false, "Build de desenvolvimento")
    override fun isInstalled(packageName: String) = false
    override fun installVirtual(apk: File, packageName: String) = Result.failure<Unit>(IllegalStateException("Motor de virtualização não incluído nesta variante"))
    override fun launchVirtual(packageName: String) = Result.failure<Unit>(IllegalStateException("Motor de virtualização não incluído nesta variante"))
    override fun removeVirtual(packageName: String) = Result.success(Unit)
}
