import 'package:shared_preferences/shared_preferences.dart';

/// 提醒状态：记录「今日某组是否已提醒过」，避免反复弹。
class ReminderState {
  bool shouldNotify({required bool overtime, required bool warned}) =>
      overtime && !warned;

  Future<void> markNotified(String date, String groupName) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool('$date|remind|$groupName', true);
  }

  Future<bool> wasNotified(String date, String groupName) async {
    final sp = await SharedPreferences.getInstance();
    return sp.getBool('$date|remind|$groupName') ?? false;
  }
}
