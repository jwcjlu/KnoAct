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
      // 真机上后台 isolate 拿不到编译期 API_BASE；优先用登录时持久化的地址。
      final baseUrl = await SessionStore().readApiBase() ?? resolveApiBase();
      // 后台 isolate 没有 Riverpod 会话：直接从本地存储取登录时保存的 access_token
      final token = await SessionStore().readAccessToken();
      final dio = Dio(BaseOptions(
        baseUrl: baseUrl,
        headers: {if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token'},
      ));
      await ScreenTimeSync(api, dio).reportDay(childId, date, day, names: names);
      await _maybeNotify(childId, date, dio, api);
    }
    return true;
  });
}

final _notifs = FlutterLocalNotificationsPlugin();

/// 拉取规则 + 读取当日时长，若超时且本组尚未提醒过则弹本地通知。
Future<void> _maybeNotify(int childId, String date, Dio dio, UsageApi api) async {
  try {
    final sync = ScreenTimeSync(api, dio);
    final rules = await sync.fetchRules(childId);
    final packageGroups = await sync.fetchPackageGroups(childId);
    final day = await api.readLocalDay(date);
    final state = ReminderState();
    final groupTotals = groupTotalsFromDay(day, packageGroups);
    for (final r in rules) {
      final overtime = isOvertime(groupTotals[r.groupId] ?? 0, r.limitSeconds);
      final warned = await state.wasNotified(date, r.name);
      if (state.shouldNotify(overtime: overtime, warned: warned)) {
        await _notifs.show(r.groupId, '该休息了', '「${r.name}」今日时长已用完', const NotificationDetails(
          android: AndroidNotificationDetails('screen_time', '屏幕时间', importance: Importance.high),
        ));
        await state.markNotified(date, r.name);
      }
    }
  } catch (_) {
    // 提醒失败不得让整个周期任务（含已完成的 reportDay）被判失败。
  }
}

String _fmt(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
