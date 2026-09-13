plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.bbl.container"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bbl.container"
        minSdk = 23
        targetSdk = 28
        versionCode = 6
        versionName = "0.3.3"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

    kotlinOptions {
        jvmTarget = "21"
    }

    flavorDimensions += "engine"
    productFlavors {
        create("stub") {
            dimension = "engine"
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
        }
        create("blackbox") {
            dimension = "engine"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.4.0")

    if (project.findProject(":Bcore") != null) {
        add("blackboxImplementation", project(":Bcore"))
    }
}
