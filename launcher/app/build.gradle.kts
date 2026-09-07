plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val apiBaseUrl = (project.findProperty("BBL_API_BASE_URL") as String?)
    ?: "https://bbl-tvbox-manager-v2.onrender.com"

android {
    namespace = "com.bbl.boxtv.launcher"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bbl.boxtv.launcher"
        minSdk = 21
        targetSdk = 35
        versionCode = 7
        versionName = "2.0.0"
        buildConfigField("String", "API_BASE_URL", "\"${apiBaseUrl.trimEnd('/')}\"")
    }

    buildFeatures { buildConfig = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions { jvmTarget = "1.8" }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
