import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/home_controller.dart';
import 'data/kp_srs_repository.dart';

/// 当前这一项提交后的反馈（非 null = 本项已提交，等孩子点「继续」）
class KpSrsFeedback {
  const KpSrsFeedback({required this.result, this.isCorrect, this.graded = false});

  /// 服务端最终采用的结果：remember / fuzzy / forgot
  final String result;
  final bool? isCorrect;
  final bool graded;

  bool get forgot => result == kpResultForgot;
}

class KpSrsState {
  const KpSrsState({
    this.started = false,
    this.taskId,
    this.title = '',
    this.items = const [],
    this.index = 0,
    this.completed = 0,
    this.loading = false,
    this.busy = false,
    this.error,
    this.answer = '',
    this.feedback,
  });

  /// init 是否已调用过（页面据此决定直接进入时是否补一次独立入口加载）
  final bool started;
  final int? taskId;
  final String title;
  final List<KpSrsItem> items;
  final int index;

  /// 本次已提交（并被服务端接受）的知识点数
  final int completed;
  final bool loading;
  final bool busy;
  final String? error;
  final String answer;
  final KpSrsFeedback? feedback;

  bool get isEmpty => started && !loading && error == null && items.isEmpty;
  bool get isDone => started && !loading && items.isNotEmpty && index >= items.length;
  KpSrsItem? get current => index >= 0 && index < items.length ? items[index] : null;

  /// 「忘了」后展开知识点原文
  bool get revealContent => feedback?.forgot ?? false;

  KpSrsState copyWith({
    bool? started,
    int? taskId,
    String? title,
    List<KpSrsItem>? items,
    int? index,
    int? completed,
    bool? loading,
    bool? busy,
    Object? error = _keep,
    String? answer,
    Object? feedback = _keep,
  }) =>
      KpSrsState(
        started: started ?? this.started,
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        items: items ?? this.items,
        index: index ?? this.index,
        completed: completed ?? this.completed,
        loading: loading ?? this.loading,
        busy: busy ?? this.busy,
        error: identical(error, _keep) ? this.error : error as String?,
        answer: answer ?? this.answer,
        feedback: identical(feedback, _keep) ? this.feedback : feedback as KpSrsFeedback?,
      );
}

const _keep = Object();

class KpSrsController extends Notifier<KpSrsState> {
  int? get _uid => ref.read(currentChildIdProvider);
  DateTime _startedAt = DateTime.now();
  int _gen = 0;

  @override
  KpSrsState build() {
    ref.watch(currentChildIdProvider);
    return const KpSrsState();
  }

  /// 双入口：
  /// - 任务入口：[content] 为 kp_review 任务快照 JSON，直接用快照；
  /// - 独立入口（[taskId] 为 null，或快照为空/损坏）：现场拉取到期项。
  Future<void> init({int? taskId, String? content, String title = ''}) async {
    final gen = ++_gen;
    _startedAt = DateTime.now();
    final snapshot = (content == null || content.isEmpty) ? const <KpSrsItem>[] : parseKpSrsContent(content);
    if (snapshot.isNotEmpty) {
      state = KpSrsState(started: true, taskId: taskId, title: title, items: snapshot);
      return;
    }
    state = KpSrsState(started: true, taskId: taskId, title: title, loading: true);
    await _loadDue(gen);
  }

  /// 加载失败后重试（独立入口）
  Future<void> retry() async {
    final gen = ++_gen;
    state = state.copyWith(loading: true, error: null);
    await _loadDue(gen);
  }

  Future<void> _loadDue(int gen) async {
    final uid = _uid;
    if (uid == null) {
      state = state.copyWith(loading: false);
      return;
    }
    try {
      final items = await ref.read(kpSrsRepositoryProvider).fetchDue(userId: uid);
      if (!ref.mounted || gen != _gen || _uid != uid) return;
      _startedAt = DateTime.now();
      state = state.copyWith(loading: false, items: items, index: 0, error: null);
    } catch (_) {
      if (!ref.mounted || gen != _gen || _uid != uid) return;
      state = state.copyWith(loading: false, error: '加载失败，请检查网络后重试');
    }
  }

  void setAnswer(String value) => state = state.copyWith(answer: value);

  /// 自评：记得 / 有点忘 / 忘了
  Future<void> selfRate(String result) => _complete(result);

  /// 带题：提交答案（服务端判分，覆盖自评）
  Future<void> submitAnswer() {
    final item = state.current;
    if (item == null || !item.prompt.hasQuestion || state.answer.trim().isEmpty) return Future.value();
    // result 仅作占位，带 question_id 时后端以判分为准
    return _complete(kpResultRemember, withQuestion: true);
  }

  Future<void> _complete(String result, {bool withQuestion = false}) async {
    final uid = _uid;
    final item = state.current;
    if (uid == null || item == null || state.busy || state.feedback != null) return;
    state = state.copyWith(busy: true, error: null);
    final gen = _gen;
    KpSrsCompleteResult? r;
    try {
      r = await ref.read(kpSrsRepositoryProvider).complete(
            userId: uid,
            itemId: item.itemId,
            result: result,
            questionId: withQuestion ? item.prompt.questionId : null,
            studentAnswer: withQuestion ? state.answer.trim() : null,
            durationMs: DateTime.now().difference(_startedAt).inMilliseconds,
          );
    } catch (_) {
      r = null;
    }
    if (!ref.mounted || gen != _gen || _uid != uid) return;
    if (r == null) {
      state = state.copyWith(busy: false, error: '提交失败，请稍后重试');
      return;
    }
    final fb = KpSrsFeedback(
      result: r.result.isEmpty ? result : r.result,
      isCorrect: r.isCorrect,
      graded: r.graded,
    );
    state = state.copyWith(busy: false, completed: state.completed + 1);
    // 需要孩子看一眼的才停下（答题反馈 / 忘了 → 展开原文）；其余直接进入下一项
    if (fb.graded || fb.forgot) {
      state = state.copyWith(feedback: fb);
    } else {
      _advance();
    }
    try {
      ref.read(homeControllerProvider.notifier).reload();
    } catch (_) {}
  }

  /// 看完反馈后继续下一项
  void next() {
    if (state.feedback == null) return;
    _advance();
  }

  void _advance() {
    _startedAt = DateTime.now();
    state = state.copyWith(index: state.index + 1, answer: '', feedback: null, error: null);
  }
}

final kpSrsControllerProvider = NotifierProvider<KpSrsController, KpSrsState>(KpSrsController.new);
