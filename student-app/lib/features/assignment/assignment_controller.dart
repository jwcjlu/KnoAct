import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
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
      );
}

class AssignmentController extends Notifier<AssignmentState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  AssignmentState build() {
    ref.watch(currentChildIdProvider);
    return const AssignmentState();
  }

  /// 从阅读页进入时初始化（lessonId + subject）
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
    final uid = _uid;
    final lessonId = state.lessonId;
    if (uid == null || lessonId == null || state.busy) return;

    final wrong = state.result != null && !state.result!.passed
        ? [for (final r in state.result!.items) if (!r.isCorrect) r.question]
        : <String>[];

    state = state.copyWith(busy: true, busyLabel: () => '正在出题…');
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
      state = state.copyWith(busy: false, busyLabel: () => null);
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
