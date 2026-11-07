import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../reader/reader_controller.dart';
import 'data/assignment_models.dart';
import 'data/assignment_repository.dart';

class AssignmentState {
  const AssignmentState({
    this.lessonId,
    this.subject = '语文',
    this.questions = const [],
    this.inputs = const [],
    this.result,
    this.busy = false,
    this.busyLabel,
    this.previousQuestions = const [],
    this.round = 0,
    this.errorMessage,
  });

  final int? lessonId;
  final String subject;
  final List<AssignmentQuestion> questions;

  /// 每题作答（与 questions 下标对齐）
  final List<String> inputs;
  final AssignmentResult? result;

  /// 正在出题/批改
  final bool busy;
  final String? busyLabel;

  /// 本课已出过的题（下一组不重复）
  final List<String> previousQuestions;
  final int round;

  /// 出题/批改失败提示（对齐 Web toast）
  final String? errorMessage;

  AssignmentState copyWith({
    int? lessonId,
    String? subject,
    List<AssignmentQuestion>? questions,
    List<String>? inputs,
    AssignmentResult? Function()? result,
    bool? busy,
    String? Function()? busyLabel,
    List<String>? previousQuestions,
    int? round,
    String? Function()? errorMessage,
  }) =>
      AssignmentState(
        lessonId: lessonId ?? this.lessonId,
        subject: subject ?? this.subject,
        questions: questions ?? this.questions,
        inputs: inputs ?? this.inputs,
        result: result != null ? result() : this.result,
        busy: busy ?? this.busy,
        busyLabel: busyLabel != null ? busyLabel() : this.busyLabel,
        previousQuestions: previousQuestions ?? this.previousQuestions,
        round: round ?? this.round,
        errorMessage: errorMessage != null ? errorMessage() : this.errorMessage,
      );
}

class AssignmentController extends Notifier<AssignmentState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  AssignmentState build() {
    // 勿 watch 会话：childId 变化会整段 rebuild 并清空题目。首屏 lessonId 从阅读器读出，切换课时时 listen 只改绑定字段。
    ref.listen(readerControllerProvider, (prev, next) {
      final id = next.currentLesson?.id;
      if (id == null) return;
      if (state.lessonId == id && state.subject == next.documentSubject) return;
      state = state.copyWith(lessonId: id, subject: next.documentSubject);
    });
    final reader = ref.read(readerControllerProvider);
    return AssignmentState(
      lessonId: reader.currentLesson?.id,
      subject: reader.documentSubject,
    );
  }

  void _bindLessonFromReader() {
    final reader = ref.read(readerControllerProvider);
    final id = reader.currentLesson?.id;
    if (id == null) return;
    if (state.lessonId == id) return;
    state = state.copyWith(lessonId: id, subject: reader.documentSubject);
  }

  /// 学习中心等场景手动绑定（`/assignment` 路由）
  void init({required int lessonId, required String subject}) {
    state = AssignmentState(lessonId: lessonId, subject: subject);
  }

  void setInput(int index, String value) {
    if (index < 0 || index >= state.inputs.length) return;
    final inputs = [...state.inputs];
    inputs[index] = value;
    state = state.copyWith(inputs: inputs);
  }

  /// 出一组题；上一组未达标时带上错题
  Future<void> generate() async {
    _bindLessonFromReader();
    final uid = _uid;
    final lessonId = state.lessonId;
    if (uid == null) {
      state = state.copyWith(errorMessage: () => '请先登录');
      return;
    }
    if (lessonId == null) {
      state = state.copyWith(errorMessage: () => '请先选择课程');
      return;
    }
    if (state.busy) return;

    final wrong = state.result != null && !state.result!.passed
        ? [for (final r in state.result!.items) if (!r.isCorrect) r.question]
        : <String>[];

    state = state.copyWith(busy: true, busyLabel: () => '正在出题…', errorMessage: () => null);
    List<AssignmentQuestion> qs;
    try {
      qs = await ref.read(assignmentRepositoryProvider).generate(
            userId: uid,
            lessonId: lessonId,
            subject: state.subject,
            previousQuestions: state.previousQuestions,
            wrongQuestions: wrong,
          );
    } catch (_) {
      qs = const [];
    }
    if (!ref.mounted || _uid != uid) return;

    if (qs.isEmpty) {
      state = state.copyWith(busy: false, busyLabel: () => null, errorMessage: () => '出题失败，请稍后再试');
      return;
    }
    state = state.copyWith(
      questions: qs,
      inputs: List.filled(qs.length, ''),
      result: () => null,
      busy: false,
      busyLabel: () => null,
      previousQuestions: [...state.previousQuestions, ...qs.map((q) => q.question)],
      round: state.round + 1,
    );
  }

  Future<void> submit() async {
    final uid = _uid;
    final lessonId = state.lessonId;
    if (uid == null || lessonId == null || state.busy || state.questions.isEmpty) return;
    if (state.inputs.any((i) => i.trim().isEmpty)) return;

    final items = [
      for (var i = 0; i < state.questions.length; i++)
        {
          'question': state.questions[i].question,
          'answer': state.questions[i].answer,
          'student_answer': state.inputs[i].trim(),
          'knowledge_point_id': state.questions[i].knowledgePointId,
        },
    ];

    state = state.copyWith(busy: true, busyLabel: () => '正在批改…');
    AssignmentResult? result;
    try {
      result = await ref.read(assignmentRepositoryProvider).grade(
            userId: uid,
            lessonId: lessonId,
            subject: state.subject,
            items: items,
          );
    } catch (_) {
      result = null;
    }
    if (!ref.mounted || _uid != uid) return;
    state = state.copyWith(busy: false, busyLabel: () => null, result: result == null ? () => null : () => result);
  }

  void cancel() {
    state = state.copyWith(
      questions: const [],
      inputs: const [],
      result: () => null,
      round: 0,
    );
  }
}

final assignmentControllerProvider = NotifierProvider<AssignmentController, AssignmentState>(AssignmentController.new);
