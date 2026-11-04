import 'package:shared_preferences/shared_preferences.dart';

import 'auth_repository.dart';

class SessionStore {
  static const childIdKey = 'knoact_child_id';
  static const apiBaseKey = 'knoact_api_base';
  static const _kId = childIdKey;
  static const _kName = 'knoact_child_name';

  Future<Child?> load() async {
    final p = await SharedPreferences.getInstance();
    final id = p.getInt(_kId);
    final name = p.getString(_kName);
    return (id != null && name != null) ? Child(id, name) : null;
  }

  Future<void> save(Child c) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kId, c.id);
    await p.setString(_kName, c.name);
  }

  /// 持久化后端地址，供后台 worker 在独立 isolate 里读取（真机上 worker 拿不到
  /// 编译期 API_BASE，也读不到主 isolate 的运行时值）。
  Future<void> saveApiBase(String baseUrl) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(apiBaseKey, baseUrl);
  }

  Future<String?> readApiBase() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(apiBaseKey);
  }

  Future<void> clear() async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_kId);
    await p.remove(_kName);
  }
}
