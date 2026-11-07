import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'data/math_models.dart';
import 'data/math_repository.dart';

class MathState {
  const MathState({
    this.taskId,
    this.title = '',
    this.detail = '',
    this.calc = const [],
    this.word = const [],
    this.calcAnswers = const [],
    this.calcResult,
    this.busy = false,
    this.loading = false,
    this.submitted = false,
    this.error,
  });

  final int? taskId;
  final String title;
  final String detail;
  final List<MathCalcItem> calc;
  final List<MathWordItem> word;
  final List<String> calcAnswers;
  final MathGradeResult? calcResult;
  final bool busy;
  final bool loading;
  final bool submitted;
  final String? error;

  bool get hasCalc => calc.isNotEmpty;
  bool get hasWord => word.isNotEmpty;

  bool get calcGraded => calc.isEmpty || calc.every((c) => c.isCorrect != null);

  bool get canGradeCalc =>
      hasCalc && !calcGraded && calcAnswers.length == calc.length && calcAnswers.every((a) => a.trim().isNotEmpty);

  bool get canSubmit =>
      !submitted &&
      (calc.isEmpty || calcGraded) &&
      (word.isEmpty || word.every((w) => w.hasPhoto && w.aiFinished)) &&
      (hasCalc || hasWord);

  MathState copyWith({
    int? taskId,
    String? title,
    String? detail,
    List<MathCalcItem>? calc,
    List<MathWordItem>? word,
    List<String>? calcAnswers,
    MathGradeResult? Function()? calcResult,
    bool? busy,
    bool? loading,
    bool? submitted,
    String? Function()? error,
  }) =>
      MathState(
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        detail: detail ?? this.detail,
        calc: calc ?? this.calc,
        word: word ?? this.word,
        calcAnswers: calcAnswers ?? this.calcAnswers,
        calcResult: calcResult != null ? calcResult() : this.calcResult,
        busy: busy ?? this.busy,
        loading: loading ?? this.loading,
        submitted: submitted ?? this.submitted,
        error: error != null ? error() : this.error,
      );
}

class MathController extends Notifier<MathState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  MathState build() {
    ref.watch(currentChildIdProvider);
    return const MathState();
  }

  void _applyMaterial(MathTaskMaterial m, {int? taskId, String? fallbackTitle}) {
    final graded = m.calcAllGraded && m.calc.isNotEmpty;
    final calcResult = graded
        ? MathGradeResult(
            correct: m.calc.where((c) => c.isCorrect == true).length,
            total: m.calc.length,
            results: [for (final c in m.calc) c.isCorrect == true],
          )
        : null;
    state = MathState(
      taskId: taskId ?? state.taskId,
      title: m.title.isNotEmpty ? m.title : (fallbackTitle ?? ''),
      detail: m.detail,
      calc: m.calc,
      word: m.word,
      calcAnswers: [for (final c in m.calc) c.yourAnswer],
      calcResult: calcResult,
    );
  }

  /// 从首页进入：拉取 material；[content] 仅作离线/旧格式兜底。
  Future<void> init({required int taskId, required String title, String content = ''}) async {
    state = MathState(taskId: taskId, title: title, loading: true);
    try {
      final material = await ref.read(mathRepositoryProvider).fetchMaterial(taskId);
      _applyMaterial(material, taskId: taskId, fallbackTitle: title);
      state = state.copyWith(loading: false);
    } catch (_) {
      final legacy = parseMathLegacyContent(content, title: title);
      if (legacy.calc.isNotEmpty) {
        _applyMaterial(legacy, taskId: taskId, fallbackTitle: title);
        state = state.copyWith(loading: false, error: () => '题目加载异常，已使用缓存内容');
      } else {
        state = MathState(taskId: taskId, title: title, loading: false, error: '无法加载数学题');
      }
    }
  }

  Future<void> reloadMaterial() async {
    final taskId = state.taskId;
    if (taskId == null) return;
    try {
      final material = await ref.read(mathRepositoryProvider).fetchMaterial(taskId);
      _applyMaterial(material, taskId: taskId, fallbackTitle: state.title);
    } catch (_) {}
  }

  void setCalcAnswer(int index, String value) {
    if (index < 0 || index >= state.calcAnswers.length) return;
    final calcAnswers = [...state.calcAnswers];
    calcAnswers[index] = value;
    state = state.copyWith(calcAnswers: calcAnswers, error: () => null);
  }

  Future<void> gradeCalc() async {
    final uid = _uid;
    final taskId = state.taskId;
    if (uid == null || taskId == null || state.busy || !state.canGradeCalc) return;

    state = state.copyWith(busy: true, error: () => null);
    try {
      final result = await ref.read(mathRepositoryProvider).gradeCalc(
            userId: uid,
            taskId: taskId,
            answers: state.calcAnswers,
          );
      if (!ref.mounted || _uid != uid) return;
      final calc = <MathCalcItem>[];
      for (var i = 0; i < state.calc.length; i++) {
        final item = state.calc[i];
        final ok = i < result.results.length ? result.results[i] : null;
        calc.add(item.copyWith(yourAnswer: state.calcAnswers[i], isCorrect: ok));
      }
      state = state.copyWith(busy: false, calc: calc, calcResult: () => result);
    } catch (e) {
      if (!ref.mounted) return;
      state = state.copyWith(busy: false, error: () => '判分失败，请稍后再试');
    }
  }

  Future<bool> uploadWordPhoto(int wordIndex, List<int> bytes, {String filename = 'math_word.jpg'}) async {
    final taskId = state.taskId;
    if (taskId == null || state.busy) return false;
    if (wordIndex < 0 || wordIndex >= state.word.length) return false;

    state = state.copyWith(busy: true, error: () => null);
    try {
      final patch = await ref.read(mathRepositoryProvider).uploadWordPhoto(taskId, wordIndex, bytes, filename: filename);
      if (!ref.mounted) return false;
      final word = [...state.word];
      final i = word.indexWhere((w) => w.index == wordIndex);
      if (i >= 0) {
        final prev = word[i];
        word[i] = prev.copyWith(
          photoPath: patch.photoPath ?? prev.photoPath,
          aiStatus: patch.aiStatus ?? prev.aiStatus,
          parentStatus: patch.parentStatus ?? prev.parentStatus,
        );
      }
      state = state.copyWith(busy: false, word: word);
      return true;
    } catch (_) {
      if (!ref.mounted) return false;
      state = state.copyWith(busy: false, error: () => '上传失败，请重试');
      return false;
    }
  }

  Future<void> submit() async {
    final taskId = state.taskId;
    if (taskId == null || state.busy || !state.canSubmit) return;

    state = state.copyWith(busy: true, error: () => null);
    try {
      await ref.read(homeRepositoryProvider).submitTask(taskId);
      if (!ref.mounted) return;
      state = state.copyWith(busy: false, submitted: true);
      try {
        ref.read(homeControllerProvider.notifier).reload();
      } catch (_) {}
    } catch (_) {
      if (!ref.mounted) return;
      state = state.copyWith(busy: false, error: () => '提交失败，请检查是否已完成所有题目');
    }
  }
}

final mathControllerProvider = NotifierProvider<MathController, MathState>(MathController.new);
