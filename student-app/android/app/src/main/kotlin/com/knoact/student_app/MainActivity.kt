package com.knoact.student_app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "knoact/usage_stats")
            .setMethodCallHandler { call, result ->
                UsageStatsPlugin(applicationContext).handle(call, result)
            }
    }
}
