package com.bbl.container

import android.content.Context
import java.io.File

data class EngineStatus(
    val name: String,
    val available: Boolean,
    val details: String
)

interface VirtualEngine {
    fun attach(context: Context) {}
    fun init(context: Context)
    fun status(): EngineStatus
    fun isInstalled(packageName: String): Boolean
    fun installVirtual(apk: File, packageName: String): Result<Unit>
    fun launchVirtual(packageName: String): Result<Unit>
    fun removeVirtual(packageName: String): Result<Unit>
}

object VirtualEngineProvider {
    lateinit var engine: VirtualEngine
        private set

    fun create(): VirtualEngine {
        if (!::engine.isInitialized) engine = BuildFlavorEngineFactory.create()
        return engine
    }
}
