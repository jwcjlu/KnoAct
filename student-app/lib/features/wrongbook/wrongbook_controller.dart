import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/wrongbook_models.dart';
import 'data/wrongbook_repository.dart';

class WrongbookState {
  const WrongbookState({
    this.subject = '全部',
    this.mistakes = const AsyncLoading<List<MistakeItem>>(),
    this.markingId,
  });

  final String subject;
  final AsyncValue<List<MistakeItem>> mistakes;

  /// 正在「标记已掌握」的错题 id；非空时该卡片显示 loading
  final int? markingId;

  WrongbookState copyWith({String? subject, AsyncValue<List<MistakeItem>>? mistakes, int? Function()? markingId}) => WrongbookState(
        subject: subject ?? this.subject,
        mistakes: mistakes ?? this.mistakes,
        markingId: markingId != null ? markingId() : this.markingId,
      );
}

class WrongbookController extends Notifier<WrongbookState> {
  int _loadToken = 0;

  int? get _uid => ref.read(currentChildIdProvider);

  @override
  WrongbookState build() {
    // 换孩子（含退出登录）时重建，清空上一个孩子的数据
    ref.watch(currentChildIdProvider);
    _loadToken++;
    return const WrongbookState();
  }

  bool _stale(int token, int uid) => !ref.mounted || token != _loadToken || _uid != uid;

  Future<void> setSubject(String subject) async {
    if (state.subject == subject) return;
    state = state.copyWith(subject: subject);
    await _load();
  }

  Future<void> reload() => _load();

  Future<void> _load() async {
    final uid = _uid;
    if (uid == null) return;
    state = state.copyWith(mistakes: const AsyncLoading());
    final token = ++_loadToken;
    final repo = ref.read(wrongbookRepositoryProvider);
    final result = await AsyncValue.guard(() => repo.list(uid, subject: state.subject));
    if (_stale(token, uid)) return;
    state = state.copyWith(mistakes: result);
  }

  Future<void> markMastered(int id) async {
    if (state.markingId != null) return;
    state = state.copyWith(markingId: () => id);
    try {
      await ref.read(wrongbookRepositoryProvider).markCorrect(id);
      if (!ref.mounted || _uid == null) return;
      // 成功移出列表
      final current = state.mistakes.value;
      if (current != null) {
        state = state.copyWith(
          mistakes: AsyncData([for (final m in current) if (m.id != id) m]),
        );
      }
    } catch (_) {
      // 失败保持原样
    } finally {
      if (ref.mounted) state = state.copyWith(markingId: () => null);
    }
  }
}

final wrongbookControllerProvider = NotifierProvider<WrongbookController, WrongbookState>(WrongbookController.new);
