import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 提醒状态：记录「今日某组是否已提醒过」，避免反复弹。
class ReminderState {
  bool shouldNotify({required bool overtime, required bool warned}) =>
      overtime && !warned;

  Future<void> markNotified(String date, String groupName) async {
    final sp = await SharedPreferences.getInstance();
    // 键与 UsageApi 的本地缓存同店共享（都以 '$date|' 开头）。这些提醒键
    // 存的是 bool 而非 int，readLocalDay 读到它们时 getInt 返回 null、按 0 计，
    // 故对当日时长汇总无影响（inert），无需单独隔离存储。
    await sp.setBool('$date|remind|$groupName', true);
  }

  Future<bool> wasNotified(String date, String groupName) async {
    final sp = await SharedPreferences.getInstance();
    return sp.getBool('$date|remind|$groupName') ?? false;
  }
}

/// 初始化通知插件并请求 Android 13+ 的 POST_NOTIFICATIONS 权限。
///
/// 仅在原生（非 Web）平台调用；失败静默吞掉，不影响启动。若权限被拒，
/// 后续 `show()` 只是不弹通知，不会抛异常。
Future<void> requestNotificationPermission() async {
  try {
    final plugin = FlutterLocalNotificationsPlugin();
    await plugin.initialize(const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    ));
    final androidImpl = plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.requestNotificationsPermission();
  } catch (_) {
    // 通知权限请求失败不阻断启动；提醒功能降级为「不弹通知」。
  }
}
