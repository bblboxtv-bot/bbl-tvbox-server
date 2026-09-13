pluginManagement {
    repositories {
        maven(url = "https://www.jitpack.io")
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven(url = "https://www.jitpack.io")
        google()
        mavenCentral()
    }
}

rootProject.name = "BBLContainer"
include(":app")

val vendorRoot = file("vendor/NewBlackbox")
val bcore = File(vendorRoot, "Bcore")
if (File(bcore, "build.gradle").exists()) {
    include(":Bcore")
    project(":Bcore").projectDir = bcore
    include(":black-reflection")
    project(":black-reflection").projectDir = File(vendorRoot, "black-reflection")
    include(":compiler")
    project(":compiler").projectDir = File(vendorRoot, "compiler")
}
