import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'data/auth_repository.dart';
import 'data/session_store.dart';

final sessionStoreProvider = Provider<SessionStore>((ref) => SessionStore());

class SessionNotifier extends AsyncNotifier<Child?> {
  @override
  Future<Child?> build() => ref.read(sessionStoreProvider).load();

  Future<void> login(String name) async {
    final child = await ref.read(authRepositoryProvider).login(name.trim());
    await ref.read(sessionStoreProvider).save(child);
    state = AsyncData(child);
  }

  Future<void> logout() async {
    await ref.read(sessionStoreProvider).clear();
    state = const AsyncData(null);
  }
}

final sessionProvider = AsyncNotifierProvider<SessionNotifier, Child?>(SessionNotifier.new);

/// 已登录孩子的 id；未登录（含退出登录的过渡期间）为 null
final currentChildIdProvider = Provider<int?>((ref) => ref.watch(sessionProvider).value?.id);
