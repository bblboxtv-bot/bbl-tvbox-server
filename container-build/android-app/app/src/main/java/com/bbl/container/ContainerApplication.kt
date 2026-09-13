package com.bbl.container

import android.app.Application
import android.content.Context
import android.util.Log

class ContainerApplication : Application() {
    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(base)
        runCatching { VirtualEngineProvider.create().attach(base) }
            .onFailure { Log.e("BBLContainer", "BlackBox attach failed", it) }
    }

    override fun onCreate() {
        super.onCreate()
    }
}
