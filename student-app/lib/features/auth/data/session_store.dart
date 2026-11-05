import 'package:shared_preferences/shared_preferences.dart';

import 'auth_repository.dart';

class SessionStore {
  static const childIdKey = 'knoact_child_id';
  static const apiBaseKey = 'knoact_api_base';
  static const accessTokenKey = 'knoact_access_token';
  static const refreshTokenKey = 'knoact_refresh_token';
  static const _kId = childIdKey;
  static const _kName = 'knoact_child_name';
  static const _kLoginName = 'knoact_login_name';
  static const _kParentBound = 'knoact_parent_bound';
  static const _kBirthMonth = 'knoact_birth_month';
  static const _kGender = 'knoact_gender';
  static const _kInterests = 'knoact_interests';

  Future<Child?> load() async {
    final p = await SharedPreferences.getInstance();
    final id = p.getInt(_kId);
    final name = p.getString(_kName);
    if (id == null || name == null) return null;
    return Child(
      id,
      name,
      loginName: p.getString(_kLoginName) ?? '',
      // 老会话没存过该字段：按已绑定处理，下次 /me 刷新后会纠正
      parentBound: p.getBool(_kParentBound) ?? true,
      birthMonth: p.getString(_kBirthMonth),
      gender: p.getString(_kGender) ?? 'unknown',
      interests: p.getString(_kInterests) ?? '',
    );
  }

  Future<void> save(Child c) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kId, c.id);
    await p.setString(_kName, c.name);
    await p.setString(_kLoginName, c.loginName);
    await p.setBool(_kParentBound, c.parentBound);
    await p.setString(_kGender, c.gender);
    await p.setString(_kInterests, c.interests);
    if (c.birthMonth == null) {
      await p.remove(_kBirthMonth);
    } else {
      await p.setString(_kBirthMonth, c.birthMonth!);
    }
  }

  Future<void> saveTokens({required String accessToken, required String refreshToken}) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(accessTokenKey, accessToken);
    await p.setString(refreshTokenKey, refreshToken);
  }

  Future<String?> readAccessToken() async => (await SharedPreferences.getInstance()).getString(accessTokenKey);

  Future<String?> readRefreshToken() async => (await SharedPreferences.getInstance()).getString(refreshTokenKey);

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
    for (final k in [
      _kId,
      _kName,
      _kLoginName,
      _kParentBound,
      _kBirthMonth,
      _kGender,
      _kInterests,
      accessTokenKey,
      refreshTokenKey,
    ]) {
      await p.remove(k);
    }
  }
}
