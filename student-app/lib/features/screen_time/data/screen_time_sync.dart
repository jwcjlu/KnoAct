import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
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
  ScreenTimeSync(this.api);

  final UsageApi api;

  /// 拉取并缓存规则（本地判超时用）。
  Future<List<ScreenRule>> fetchRules(int childId, String baseUrl) async {
    // baseUrl 由 ApiClient 提供；这里简化为直接 http 调用由上层注入。
    // 实际实现经 dio GET /api/screen-time/groups?user_id=
    return [];
  }

  /// 计算某组今日是否超时（本地缓存数据）。
  ///
  /// 契约：`daySeconds` 必须是**已按该组预过滤**的 map —— 其 key 仅为该
  /// 分组内的 package，值为各自当日累计秒数。调用方（Task 7）负责先筛出
  /// 该 rule 所辖的 package 再传入；此处直接把 `daySeconds.values` 全部累加，
  /// 不会自行按 groupId 过滤。
  bool groupOvertime(Map<String, int> daySeconds, ScreenRule rule) {
    final total = daySeconds.values.fold<int>(0, (a, b) => a + b);
    return isOvertime(total, rule.limitSeconds);
  }
}
