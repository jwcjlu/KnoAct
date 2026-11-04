import 'package:workmanager/workmanager.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import '../../auth/data/session_store.dart';
import '../../../core/config.dart';
import 'usage_api.dart';
import 'screen_time_sync.dart';
import 'screen_time_notifier.dart';

const screenTimeTaskName = 'knoact.screenTime.sync';

/// WorkManager 后台任务：采样 + 上报。周期 15 分钟（Android 下限）。
void registerScreenTimeWorker() {
  Workmanager().initialize(callbackDispatcher);
  Workmanager().registerPeriodicTask(
    screenTimeTaskName, screenTimeTaskName,
    frequency: const Duration(minutes: 15),
  );
}

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    final api = UsageApi();
    final sp = await SharedPreferences.getInstance();
    final since = sp.getInt('last_sync_ms') ?? 0;
    final now = DateTime.now();
    final date = _fmt(now);
    final stats = await api.queryUsage(since);
    for (final s in stats) {
      await api.addLocalSeconds(date, s.package, s.appName, s.durationMs ~/ 1000);
    }
    await sp.setInt('last_sync_ms', now.millisecondsSinceEpoch);
    final childId = sp.getInt(SessionStore.childIdKey) ?? 0;
    if (childId != 0) {
      final day = await api.readLocalDay(date);
      final names = await api.readLocalNames(date);
      final dio = Dio(BaseOptions(baseUrl: resolveApiBase()));
      await ScreenTimeSync(api, dio).reportDay(childId, date, day, names: names);
      await _maybeNotify(childId, date, dio, api);
    }
    return true;
  });
}

final _notifs = FlutterLocalNotificationsPlugin();

/// 拉取规则 + 读取当日时长，若超时且本组尚未提醒过则弹本地通知。
Future<void> _maybeNotify(int childId, String date, Dio dio, UsageApi api) async {
  final rules = await ScreenTimeSync(api, dio).fetchRules(childId);
  final day = await api.readLocalDay(date);
  final state = ReminderState();
  // 简化：把当日「所有包」时长合计，逐个与娱乐/有限制组的 limit 比较。
  // 按组精确过滤 day 需要包名→组映射，worker 本地没有，故以日总量近似。
  final total = day.values.fold<int>(0, (a, b) => a + b);
  for (final r in rules.where((r) => r.kind == 'fun' || r.limitSeconds != null)) {
    final overtime = isOvertime(total, r.limitSeconds);
    final warned = await state.wasNotified(date, r.name);
    if (state.shouldNotify(overtime: overtime, warned: warned)) {
      await _notifs.show(0, '该休息了', '「${r.name}」今日时长已用完', const NotificationDetails(
        android: AndroidNotificationDetails('screen_time', '屏幕时间', importance: Importance.high),
      ));
      await state.markNotified(date, r.name);
    }
  }
}

String _fmt(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
