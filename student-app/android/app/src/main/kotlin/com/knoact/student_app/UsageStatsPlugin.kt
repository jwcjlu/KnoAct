package com.knoact.student_app

import android.app.usage.UsageStats
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

class UsageStatsPlugin(private val context: Context) {

    private val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

    fun handle(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "hasUsageAccess" -> result.success(hasUsageAccess())
            "openUsageAccessSettings" -> {
                context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
                result.success(true)
            }
            "queryUsage" -> {
                val since = (call.argument<Number>("since") ?: 0L).toLong()
                result.success(queryUsage(since))
            }
            else -> result.notImplemented()
        }
    }

    private fun hasUsageAccess(): Boolean {
        val am = context.getSystemService(Context.APP_OPS_SERVICE) as android.app.AppOpsManager
        val mode = am.unsafeCheckOpNoThrow(
            android.app.AppOpsManager.OPSTR_GET_USAGE_STATS,
            android.os.Process.myUid(), context.packageName)
        return mode == android.app.AppOpsManager.MODE_ALLOWED
    }

    private fun queryUsage(since: Long): List<Map<String, Any>> {
        if (!hasUsageAccess()) return emptyList()
        val now = System.currentTimeMillis()
        val stats: List<UsageStats> = usm.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY, since, now)
        val pm = context.packageManager
        val out = mutableListOf<Map<String, Any>>()
        for (s in stats) {
            val total = s.totalTimeInForeground
            if (total <= 0) continue
            var label = s.packageName
            try {
                label = pm.getApplicationLabel(pm.getApplicationInfo(s.packageName, 0)).toString()
            } catch (_: PackageManager.NameNotFoundException) {
            }
            out.add(mapOf("package" to s.packageName, "appName" to label, "durationMs" to total))
        }
        return out
    }
}
