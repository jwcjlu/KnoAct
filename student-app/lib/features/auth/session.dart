import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/config.dart';
import 'data/auth_repository.dart';
import 'data/session_store.dart';

final sessionStoreProvider = Provider<SessionStore>((ref) => SessionStore());

class SessionNotifier extends AsyncNotifier<Child?> {
  @override
  Future<Child?> build() async {
    final store = ref.read(sessionStoreProvider);
    final cached = await store.load();
    if (cached == null) return null;
    // 有令牌时向 /me 校准 parent_bound 等字段；网络失败沿用缓存，401 由 ApiClient 触发 [expire]
    if (await store.readAccessToken() == null) return cached;
    try {
      final fresh = await ref.read(authRepositoryProvider).me().timeout(const Duration(seconds: 5));
      await store.save(fresh);
      return fresh;
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await store.clear();
        return null;
      }
      return cached;
    } catch (_) {
      return cached;
    }
  }

  Future<void> _start(AuthSession s) async {
    final store = ref.read(sessionStoreProvider);
    await store.saveTokens(accessToken: s.accessToken, refreshToken: s.refreshToken);
    await store.save(s.child);
    await store.saveApiBase(resolveApiBase());
    state = AsyncData(s.child);
  }

  /// 登录名 + 密码登录
  Future<void> login(String loginName, String password) async =>
      _start(await ref.read(authRepositoryProvider).login(loginName.trim(), password));

  /// 注册孩子账号（成功后自动登录）
  Future<void> register(String loginName, String password) async =>
      _start(await ref.read(authRepositoryProvider).register(loginName.trim(), password));

  Future<void> sendOtp(String loginName) => ref.read(authRepositoryProvider).sendOtp(loginName.trim());

  Future<void> otpLogin(String loginName, String code) async =>
      _start(await ref.read(authRepositoryProvider).otpLogin(loginName.trim(), code.trim()));

  /// 重新拉取 /me（绑定家长、编辑资料后调用）
  Future<void> refreshMe() async {
    final fresh = await ref.read(authRepositoryProvider).me();
    await ref.read(sessionStoreProvider).save(fresh);
    state = AsyncData(fresh);
  }

  Future<void> updateProfile({
    required String displayName,
    String? birthMonth,
    required String gender,
    required String interests,
  }) async {
    final fresh = await ref.read(authRepositoryProvider).updateProfile(
          displayName: displayName,
          birthMonth: birthMonth,
          gender: gender,
          interests: interests,
        );
    await ref.read(sessionStoreProvider).save(fresh);
    state = AsyncData(fresh);
  }

  /// 邀请码绑定，成功后刷新会话（router 随之放行主界面）
  Future<void> bindByCode(String code) async {
    await ref.read(authRepositoryProvider).bindByCode(code.trim());
    await refreshMe();
  }

  /// 向家长发起绑定申请；需家长审批，不改变会话
  Future<void> requestParent(String parentLoginName) =>
      ref.read(authRepositoryProvider).requestParent(parentLoginName.trim());

  Future<void> logout() async {
    await ref.read(sessionStoreProvider).clear();
    state = const AsyncData(null);
  }

  /// 令牌失效（401）：清除会话回到登录页
  Future<void> expire() async {
    if (state.value == null) return;
    await logout();
  }
}

final sessionProvider = AsyncNotifierProvider<SessionNotifier, Child?>(SessionNotifier.new);

/// 已登录孩子的 id；未登录（含退出登录的过渡期间）为 null
final currentChildIdProvider = Provider<int?>((ref) => ref.watch(sessionProvider).value?.id);
