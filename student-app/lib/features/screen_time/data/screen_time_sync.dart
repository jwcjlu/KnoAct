import 'package:dio/dio.dart';
import 'usage_api.dart';

/// 超时：超过 daily_limit_seconds（null = 不限）。
bool isOvertime(int seconds, int? limit) =>
    limit != null && seconds > limit;

/// 预警：达到上限的 80%。
bool hitWarnThreshold(int seconds, int? limit) =>
    limit != null && seconds >= limit * 0.8;

class ScreenRule {
  ScreenRule({required this.groupId, required this.name, required this.kind, this.limitSeconds});
  final int groupId;
  final String name;
  final String kind;
  final int? limitSeconds;
}

/// 上报本地累计时长到后端，拉取规则并做本地超时提醒。
class ScreenTimeSync {
  ScreenTimeSync(this.api, this.dio);

  final UsageApi api;
  final Dio dio;

  Future<List<ScreenRule>> fetchRules(int childId) async {
    final r = await dio.get('/api/screen-time/groups', queryParameters: {'user_id': childId});
    final data = r.data as Map<String, dynamic>;
    final groups = (data['groups'] as List).whereType<Map<String, dynamic>>();
    return groups
        .map((g) => ScreenRule(
              groupId: g['id'] as int,
              name: g['name'] as String,
              kind: g['kind'] as String,
              limitSeconds: g['daily_limit_seconds'] as int?,
            ))
        .toList();
  }

  /// 把某天本地缓存的「包名→秒」上报后端（累加语义由后端保证）。
  /// [names] 可选：包名→显示名，用于填充 app_name。
  Future<void> reportDay(int childId, String date, Map<String, int> daySeconds,
      {Map<String, String> names = const {}}) async {
    if (daySeconds.isEmpty) return;
    final items = daySeconds.entries
        .map((e) => {
              'app_package': e.key,
              'app_name': names[e.key] ?? '',
              'duration_seconds': e.value
            })
        .toList();
    await dio.post('/api/screen-time/report',
        data: {'child_id': childId, 'date': date, 'items': items});
  }
}
