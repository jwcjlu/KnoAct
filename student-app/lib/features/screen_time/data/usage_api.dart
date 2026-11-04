import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

class UsageStats {
  UsageStats(this.package, this.appName, this.durationMs);
  final String package;
  final String appName;
  final int durationMs;
}

/// 与原生 UsageStatsPlugin 通信；本地缓存每日累计时长。
class UsageApi {
  static const _channel = MethodChannel('knoact/usage_stats');

  Future<bool> hasUsageAccess() async =>
      await _channel.invokeMethod<bool>('hasUsageAccess') ?? false;

  Future<void> openUsageAccessSettings() async =>
      _channel.invokeMethod('openUsageAccessSettings');

  /// since = 上次采样时间戳(ms)；返回增量后本地累加并按日聚合。
  Future<List<UsageStats>> queryUsage(int sinceMs) async {
    final raw = await _channel.invokeListMethod<dynamic>('queryUsage', {'since': sinceMs});
    if (raw == null) return [];
    return raw
        .whereType<Map>()
        .map((m) => UsageStats(
              m['package'] as String,
              (m['appName'] as String?) ?? m['package'] as String,
              (m['durationMs'] as num).toInt(),
            ))
        .toList();
  }

  /// 本地缓存累计：{ '2026-11-04|com.douyin': 秒数 }
  Future<void> addLocalSeconds(String date, String package, String appName, int seconds) async {
    final sp = await SharedPreferences.getInstance();
    final key = '$date|$package';
    final prev = sp.getInt(key) ?? 0;
    await sp.setInt(key, prev + seconds);
    await sp.setString('$key.name', appName);
  }

  Future<Map<String, int>> readLocalDay(String date) async {
    final sp = await SharedPreferences.getInstance();
    final out = <String, int>{};
    for (final k in sp.getKeys()) {
      if (!k.startsWith('$date|') || k.contains('.name')) continue;
      final pkg = k.substring(date.length + 1);
      out[pkg] = sp.getInt(k) ?? 0;
    }
    return out;
  }

  Future<void> clearLocalDay(String date) async {
    final sp = await SharedPreferences.getInstance();
    for (final k in sp.getKeys().toList()) {
      if (k.startsWith('$date|')) await sp.remove(k);
    }
  }
}
