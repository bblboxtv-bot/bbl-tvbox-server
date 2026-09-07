plugins {
    id("com.android.application")
}

android {
    namespace = "com.bbl.boxtv.revenda"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bbl.boxtv.revenda"
        minSdk = 21
        targetSdk = 35
        versionCode = 4
        versionName = "2.0.2"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
