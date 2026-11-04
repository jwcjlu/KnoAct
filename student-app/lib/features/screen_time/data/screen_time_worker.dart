import 'package:workmanager/workmanager.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import '../../auth/data/session_store.dart';
import '../../../core/config.dart';
import 'usage_api.dart';
import 'screen_time_sync.dart';

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
    }
    return true;
  });
}

String _fmt(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
