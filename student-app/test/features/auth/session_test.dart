import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';

/// 假认证仓库：[result] 为 [Child]（成功，附带固定令牌）或要抛出的异常
class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository(this.result);
  final Object result;
  String? lastLoginName;
  String? lastPassword;
  String? lastCode;
  String? lastBindCode;
  String? lastParentLoginName;
  String? lastRegisterName;

  /// /me 的返回；为 null 时返回 [result]（若为 Child）
  Object? meResult;
  int meCalls = 0;
  bool otpSent = false;
  Map<String, Object?>? lastProfile;

  AuthSession _session() {
    if (result is Child) return AuthSession(result as Child, accessToken: 'acc-1', refreshToken: 'ref-1');
    throw result;
  }

  @override
  Future<AuthSession> login(String loginName, String password) async {
    lastLoginName = loginName;
    lastPassword = password;
    return _session();
  }

  @override
  Future<AuthSession> register(String loginName, String password) async {
    lastRegisterName = loginName;
    lastPassword = password;
    return _session();
  }

  @override
  Future<void> sendOtp(String loginName) async {
    lastLoginName = loginName;
    otpSent = true;
  }

  @override
  Future<AuthSession> otpLogin(String loginName, String code) async {
    lastLoginName = loginName;
    lastCode = code;
    return _session();
  }

  @override
  Future<Child> me() async {
    meCalls++;
    final r = meResult ?? result;
    if (r is Child) return r;
    throw r;
  }

  @override
  Future<Child> updateProfile({
    required String displayName,
    String? birthMonth,
    required String gender,
    required String interests,
  }) async {
    lastProfile = {'display_name': displayName, 'birth_month': birthMonth, 'gender': gender, 'interests': interests};
    final base = result as Child;
    return Child(base.id, displayName,
        loginName: base.loginName, parentBound: base.parentBound, birthMonth: birthMonth, gender: gender, interests: interests);
  }

  @override
  Future<void> bindByCode(String code) async {
    lastBindCode = code;
    final r = meResult;
    if (r is Exception) throw r;
  }

  @override
  Future<void> requestParent(String parentLoginName) async {
    lastParentLoginName = parentLoginName;
  }
}

const kChild = Child(4, '金同学', loginName: 'jin');

ProviderContainer makeContainer(AuthRepository repo) {
  final c = ProviderContainer(
    overrides: [authRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(c.dispose);
  return c;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('未登录时会话为 null', () async {
    final c = makeContainer(FakeAuthRepository(kChild));
    expect(await c.read(sessionProvider.future), isNull);
  });

  test('仅有旧版 id/name 缓存、无令牌时视为未登录并清缓存', () async {
    SharedPreferences.setMockInitialValues({
      SessionStore.childIdKey: 4,
      'knoact_child_name': '金同学',
    });
    final c = makeContainer(FakeAuthRepository(kChild));
    expect(await c.read(sessionProvider.future), isNull);
    expect(await c.read(sessionStoreProvider).load(), isNull);
  });

  test('登录成功后保存用户与令牌，并可在重建后恢复', () async {
    final repo = FakeAuthRepository(kChild);
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('  jin ', 'pw123456');
    expect(repo.lastLoginName, 'jin');
    expect(repo.lastPassword, 'pw123456');
    expect(c.read(sessionProvider).value, kChild);

    final store = c.read(sessionStoreProvider);
    expect(await store.readAccessToken(), 'acc-1');
    expect(await store.readRefreshToken(), 'ref-1');

    final c2 = makeContainer(repo);
    expect(await c2.read(sessionProvider.future), kChild);
    expect(repo.meCalls, 1, reason: '有令牌时启动会向 /me 校准');
  });

  test('启动时 /me 返回的 parent_bound 覆盖缓存', () async {
    final repo = FakeAuthRepository(const Child(4, '金同学', loginName: 'jin', parentBound: false));
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    expect(c.read(sessionProvider).value!.parentBound, isFalse);

    repo.meResult = kChild; // 家长已在别处通过申请
    final c2 = makeContainer(repo);
    expect((await c2.read(sessionProvider.future))!.parentBound, isTrue);
  });

  test('启动时 /me 网络失败沿用缓存', () async {
    final repo = FakeAuthRepository(kChild);
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    repo.meResult = ApiException('boom');
    final c2 = makeContainer(repo);
    expect(await c2.read(sessionProvider.future), kChild);
  });

  test('启动时 /me 返回 401 清除会话', () async {
    final repo = FakeAuthRepository(kChild);
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    repo.meResult = ApiException('unauthorized', statusCode: 401);
    final c2 = makeContainer(repo);
    expect(await c2.read(sessionProvider.future), isNull);
    expect(await c2.read(sessionStoreProvider).readAccessToken(), isNull);
  });

  test('注册成功后直接登录', () async {
    final repo = FakeAuthRepository(const Child(9, 'new', loginName: 'new', parentBound: false));
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).register(' new ', 'pw123456');
    expect(repo.lastRegisterName, 'new');
    expect(c.read(sessionProvider).value!.parentBound, isFalse);
    expect(await c.read(sessionStoreProvider).readAccessToken(), 'acc-1');
  });

  test('验证码登录', () async {
    final repo = FakeAuthRepository(kChild);
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).sendOtp('jin');
    expect(repo.otpSent, isTrue);
    await c.read(sessionProvider.notifier).otpLogin('jin', ' 123456 ');
    expect(repo.lastCode, '123456');
    expect(c.read(sessionProvider).value, kChild);
  });

  test('登录到非孩子账号时抛 NotAChildException 且不保存', () async {
    final c = makeContainer(FakeAuthRepository(NotAChildException()));
    await c.read(sessionProvider.future);
    await expectLater(c.read(sessionProvider.notifier).login('dad', 'pw123456'), throwsA(isA<NotAChildException>()));
    expect(c.read(sessionProvider).value, isNull);
    expect(await c.read(sessionStoreProvider).readAccessToken(), isNull);
  });

  test('邀请码绑定成功后刷新 parent_bound', () async {
    final repo = FakeAuthRepository(const Child(4, '金同学', loginName: 'jin', parentBound: false));
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    repo.meResult = kChild;
    await c.read(sessionProvider.notifier).bindByCode(' ab12cd34 ');
    expect(repo.lastBindCode, 'ab12cd34');
    expect(c.read(sessionProvider).value!.parentBound, isTrue);
  });

  test('向家长发申请不改变会话', () async {
    final repo = FakeAuthRepository(const Child(4, '金同学', loginName: 'jin', parentBound: false));
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    await c.read(sessionProvider.notifier).requestParent(' mom ');
    expect(repo.lastParentLoginName, 'mom');
    expect(c.read(sessionProvider).value!.parentBound, isFalse);
  });

  test('编辑资料后会话与存储更新', () async {
    final repo = FakeAuthRepository(kChild);
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    await c.read(sessionProvider.notifier).updateProfile(
        displayName: '小金', birthMonth: '2016-09', gender: 'male', interests: '画画,足球');
    final s = c.read(sessionProvider).value!;
    expect((s.name, s.birthMonth, s.gender, s.interests, s.loginName), ('小金', '2016-09', 'male', '画画,足球', 'jin'));
    expect(await SessionStore().load(), s);
  });

  test('退出登录清除用户与令牌', () async {
    final c = makeContainer(FakeAuthRepository(kChild));
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    await c.read(sessionProvider.notifier).logout();
    expect(c.read(sessionProvider).value, isNull);
    expect(await c.read(sessionStoreProvider).readAccessToken(), isNull);
    expect(await c.read(sessionStoreProvider).readRefreshToken(), isNull);
    final c2 = makeContainer(FakeAuthRepository(kChild));
    expect(await c2.read(sessionProvider.future), isNull);
  });

  test('expire（401）清除会话', () async {
    final c = makeContainer(FakeAuthRepository(kChild));
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('jin', 'pw123456');
    await c.read(sessionProvider.notifier).expire();
    expect(c.read(sessionProvider).value, isNull);
    expect(await c.read(sessionStoreProvider).readAccessToken(), isNull);
  });
}
