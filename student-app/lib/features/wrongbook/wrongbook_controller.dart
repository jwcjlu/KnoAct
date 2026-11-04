import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/bucket_models.dart';
import 'data/wrongbook_models.dart';
import 'data/wrongbook_repository.dart';

class WrongbookState {
  const WrongbookState({
    this.subject = '全部',
    this.mistakes = const AsyncLoading<List<MistakeItem>>(),
    this.markingId,
    this.buckets = const [],
    this.bucketId,
    this.isReadOnly = false,
  });

  final String subject;
  final AsyncValue<List<MistakeItem>> mistakes;

  /// 正在「标记已掌握」的错题 id；非空时该卡片显示 loading
  final int? markingId;

  /// 学年桶列表（active + archived）
  final List<BucketInfo> buckets;

  /// 选中的学年桶 id；null 表示尚未解析（首次加载中）
  final int? bucketId;

  /// 选中桶是否为历史学年（只读）
  final bool isReadOnly;

  WrongbookState copyWith({
    String? subject,
    AsyncValue<List<MistakeItem>>? mistakes,
    int? Function()? markingId,
    List<BucketInfo>? buckets,
    int? Function()? bucketId,
    bool? isReadOnly,
  }) =>
      WrongbookState(
        subject: subject ?? this.subject,
        mistakes: mistakes ?? this.mistakes,
        markingId: markingId != null ? markingId() : this.markingId,
        buckets: buckets ?? this.buckets,
        bucketId: bucketId != null ? bucketId() : this.bucketId,
        isReadOnly: isReadOnly ?? this.isReadOnly,
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

  Future<void> setBucket(int id) async {
    if (state.bucketId == id) return;
    final bucket = _bucket(id);
    state = state.copyWith(
      bucketId: () => id,
      isReadOnly: bucket == null ? false : !bucket.isActive,
    );
    await _load();
  }

  BucketInfo? _bucket(int id) {
    for (final b in state.buckets) {
      if (b.id == id) return b;
    }
    return null;
  }

  Future<void> reload() => _load();

  Future<void> _load() async {
    final uid = _uid;
    if (uid == null) return;
    state = state.copyWith(mistakes: const AsyncLoading());
    final token = ++_loadToken;
    final repo = ref.read(wrongbookRepositoryProvider);

    // 首次（尚未解析桶）时一并拉取学年桶，解析出默认选中的 active 桶
    if (state.bucketId == null) {
      final bucketsResult = await AsyncValue.guard(() => repo.buckets(uid));
      if (_stale(token, uid)) return;
      final buckets = bucketsResult.value ?? const <BucketInfo>[];
      final active = buckets.where((b) => b.isActive);
      final selected = active.isNotEmpty ? active.first : (buckets.isNotEmpty ? buckets.first : null);
      state = state.copyWith(
        buckets: buckets,
        bucketId: () => selected?.id,
        isReadOnly: selected == null ? false : !selected.isActive,
      );
    }

    final result = await AsyncValue.guard(() => repo.list(uid, subject: state.subject, bucketId: state.bucketId));
    if (_stale(token, uid)) return;
    state = state.copyWith(mistakes: result);
  }

  Future<void> markMastered(int id) async {
    if (state.markingId != null) return;
    // 历史学年（archived 桶）只读，标记掌握不可用
    if (state.isReadOnly) return;
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
