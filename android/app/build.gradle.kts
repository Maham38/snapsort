plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val releaseStoreFile = providers.gradleProperty("SNAPSORT_RELEASE_STORE_FILE")
    .orElse(System.getenv("SNAPSORT_RELEASE_STORE_FILE") ?: "")
    .orNull?.takeIf { it.isNotBlank() }
val releaseStorePassword = providers.gradleProperty("SNAPSORT_RELEASE_STORE_PASSWORD")
    .orElse(System.getenv("SNAPSORT_RELEASE_STORE_PASSWORD") ?: "")
    .orNull?.takeIf { it.isNotBlank() }
val releaseKeyAlias = providers.gradleProperty("SNAPSORT_RELEASE_KEY_ALIAS")
    .orElse(System.getenv("SNAPSORT_RELEASE_KEY_ALIAS") ?: "")
    .orNull?.takeIf { it.isNotBlank() }
val releaseKeyPassword = providers.gradleProperty("SNAPSORT_RELEASE_KEY_PASSWORD")
    .orElse(System.getenv("SNAPSORT_RELEASE_KEY_PASSWORD") ?: "")
    .orNull?.takeIf { it.isNotBlank() }

android {
    namespace = "com.example.snapsort"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.example.snapsort"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.create("release") {
                storeFile = releaseStoreFile?.let(::file)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
