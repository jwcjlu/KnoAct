import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'data/math_repository.dart';

class MathState {
  const MathState({
    this.taskId,
    this.title = '',
    this.questions = const [],
    this.answers = const [],
    this.result,
    this.busy = false,
  });

  final int? taskId;
  final String title;
  final List<MathQuestion> questions;
  final List<String> answers;
  final MathGradeResult? result;
  final bool busy;

  MathState copyWith({
    int? taskId,
    String? title,
    List<MathQuestion>? questions,
    List<String>? answers,
    MathGradeResult? Function()? result,
    bool? busy,
  }) =>
      MathState(
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        questions: questions ?? this.questions,
        answers: answers ?? this.answers,
        result: result != null ? result() : this.result,
        busy: busy ?? this.busy,
      );
}

class MathController extends Notifier<MathState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  MathState build() {
    ref.watch(currentChildIdProvider);
    return const MathState();
  }

  /// 从首页任务进入：解析 content，若已批改则带出结果
  void init({required int taskId, required String title, required String content}) {
    final questions = parseMathContent(content);
    // 已批改过（每题都有 is_correct）则直接显示结果
    final graded = questions.isNotEmpty && questions.every((q) => q.isCorrect != null);
    final result = graded
        ? MathGradeResult(
            correct: questions.where((q) => q.isCorrect == true).length,
            total: questions.length,
            results: [for (final q in questions) q.isCorrect == true],
          )
        : null;
    state = MathState(
      taskId: taskId,
      title: title,
      questions: questions,
      answers: [for (final q in questions) q.yourAnswer],
      result: result,
    );
  }

  void setAnswer(int index, String value) {
    if (index < 0 || index >= state.answers.length) return;
    final answers = [...state.answers];
    answers[index] = value;
    state = state.copyWith(answers: answers);
  }

  Future<void> submit() async {
    final uid = _uid;
    final taskId = state.taskId;
    if (uid == null || taskId == null || state.busy || state.result != null) return;
    if (state.answers.any((a) => a.trim().isEmpty)) return;

    state = state.copyWith(busy: true);
    MathGradeResult? result;
    try {
      result = await ref.read(mathRepositoryProvider).grade(
            userId: uid,
            taskId: taskId,
            answers: state.answers,
          );
      // 判分成功后提交任务（待家长确认）
      await ref.read(homeRepositoryProvider).submitTask(taskId);
    } catch (_) {
      result = null;
    }
    if (!ref.mounted || _uid != uid) return;
    state = state.copyWith(busy: false, result: result == null ? () => null : () => result);
    // 刷新首页任务状态
    if (result != null) {
      try {
        ref.read(homeControllerProvider.notifier).reload();
      } catch (_) {}
    }
  }
}

final mathControllerProvider = NotifierProvider<MathController, MathState>(MathController.new);
