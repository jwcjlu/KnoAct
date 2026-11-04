import 'package:shared_preferences/shared_preferences.dart';

import 'auth_repository.dart';

class SessionStore {
  static const childIdKey = 'knoact_child_id';
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

  Future<void> clear() async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_kId);
    await p.remove(_kName);
  }
}
