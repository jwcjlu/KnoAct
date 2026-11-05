import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

class Child {
  const Child(
    this.id,
    this.name, {
    this.loginName = '',
    this.parentBound = true,
    this.birthMonth,
    this.gender = 'unknown',
    this.interests = '',
  });

  final int id;

  /// 展示名（后端 `display_name`，缺省回落 `name`）
  final String name;

  /// 登录名（只读）
  final String loginName;
  final bool parentBound;

  /// `YYYY-MM`，未设置为 null
  final String? birthMonth;

  /// `male` / `female` / `unknown`
  final String gender;

  /// 逗号分隔的兴趣
  final String interests;

  factory Child.fromUserJson(Map<String, dynamic> d) => Child(
        (d['id'] as num).toInt(),
        (d['display_name'] as String?)?.isNotEmpty == true ? d['display_name'] as String : (d['name'] as String? ?? ''),
        loginName: d['login_name'] as String? ?? '',
        parentBound: d['parent_bound'] == true,
        birthMonth: (d['birth_month'] as String?)?.isEmpty == true ? null : d['birth_month'] as String?,
        gender: d['gender'] as String? ?? 'unknown',
        interests: d['interests'] as String? ?? '',
      );

  Child copyWith({bool? parentBound}) => Child(
        id,
        name,
        loginName: loginName,
        parentBound: parentBound ?? this.parentBound,
        birthMonth: birthMonth,
        gender: gender,
        interests: interests,
      );

  @override
  bool operator ==(Object other) =>
      other is Child &&
      other.id == id &&
      other.name == name &&
      other.loginName == loginName &&
      other.parentBound == parentBound &&
      other.birthMonth == birthMonth &&
      other.gender == gender &&
      other.interests == interests;

  @override
  int get hashCode => Object.hash(id, name, loginName, parentBound, birthMonth, gender, interests);
}

/// 登录/注册成功的结果：用户 + 令牌
class AuthSession {
  const AuthSession(this.child, {required this.accessToken, required this.refreshToken});

  final Child child;
  final String accessToken;
  final String refreshToken;
}

class NotAChildException implements Exception {}

class AuthRepository {
  AuthRepository(this._api);

  final ApiClient _api;

  AuthSession _session(Object? data) {
    final d = asMap(data);
    final user = asMap(d['user']);
    if (user['role'] != 'child') throw NotAChildException();
    return AuthSession(
      Child.fromUserJson(user),
      accessToken: d['access_token'] as String,
      refreshToken: d['refresh_token'] as String? ?? '',
    );
  }

  /// 登录名 + 密码登录。非孩子账号抛 [NotAChildException]。
  Future<AuthSession> login(String loginName, String password) async =>
      _session(await _api.post('/api/auth/login', body: {'login_name': loginName, 'password': password}));

  /// 注册孩子账号并直接登录
  Future<AuthSession> register(String loginName, String password) async => _session(
      await _api.post('/api/auth/register', body: {'login_name': loginName, 'password': password, 'role': 'child'}));

  Future<void> sendOtp(String loginName) async {
    await _api.post('/api/auth/otp/send', body: {'login_name': loginName, 'purpose': 'login'});
  }

  Future<AuthSession> otpLogin(String loginName, String code) async =>
      _session(await _api.post('/api/auth/otp/login', body: {'login_name': loginName, 'code': code}));

  Future<Child> me() async => Child.fromUserJson(asMap(await _api.get('/api/auth/me')));

  Future<Child> updateProfile({
    required String displayName,
    String? birthMonth,
    required String gender,
    required String interests,
  }) async =>
      Child.fromUserJson(asMap(await _api.patch('/api/auth/me/profile', body: {
        'display_name': displayName,
        'birth_month': birthMonth,
        'gender': gender,
        'interests': interests,
      })));

  /// 家长邀请码绑定
  Future<void> bindByCode(String code) async {
    await _api.post('/api/family/bind', body: {'code': code});
  }

  /// 向家长登录名发起绑定申请（待家长审批）
  Future<void> requestParent(String parentLoginName) async {
    await _api.post('/api/family/request', body: {'parent_login_name': parentLoginName});
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) => AuthRepository(ref.watch(apiClientProvider)));
