plugins {
    id("com.android.application") version "8.7.3" apply false
    id("com.android.library") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
}
extra["compileSdkVersion"] = 35
extra["minSdk"] = 23
extra["targetSdkVersion"] = 28
