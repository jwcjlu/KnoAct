import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../reader/reader_controller.dart';
import 'ask_controller.dart';
import 'data/read_ask_cards_models.dart';
import 'data/read_ask_cards_repository.dart';

class ImmersiveQuizState {
  const ImmersiveQuizState({
    this.quizId,
    this.questions = const [],
    this.answers = const {},
    this.submitted = false,
    this.results = const [],
    this.busy = false,
    this.error,
  });

  final int? quizId;
  final List<ReaderQuizQuestion> questions;
  final Map<String, int> answers;
  final bool submitted;
  final List<ReaderQuizGradeRow> results;
  final bool busy;
  final String? error;

  bool get active => questions.isNotEmpty;

  ImmersiveQuizState copyWith({
    int? Function()? quizId,
    List<ReaderQuizQuestion>? questions,
    Map<String, int>? answers,
    bool? submitted,
    List<ReaderQuizGradeRow>? results,
    bool? busy,
    String? Function()? error,
  }) =>
      ImmersiveQuizState(
        quizId: quizId != null ? quizId() : this.quizId,
        questions: questions ?? this.questions,
        answers: answers ?? this.answers,
        submitted: submitted ?? this.submitted,
        results: results ?? this.results,
        busy: busy ?? this.busy,
        error: error != null ? error() : this.error,
      );
}

class ImmersiveQuizController extends Notifier<ImmersiveQuizState> {
  @override
  ImmersiveQuizState build() {
    ref.listen<int?>(
      readerControllerProvider.select((s) => s.currentLesson?.id),
      (prev, next) {
        if (prev != next) state = const ImmersiveQuizState();
      },
    );
    return const ImmersiveQuizState();
  }

  Future<void> start() async {
    ref.read(askControllerProvider.notifier).ensureReaderBound();
    final lessonId = ref.read(askControllerProvider).lessonId;
    if (lessonId == null || state.busy) return;
    state = state.copyWith(busy: true, error: () => null, questions: const [], submitted: false, results: const []);
    final repo = ref.read(readAskCardsRepositoryProvider);
    final r = await repo.generateQuiz(lessonId: lessonId);
    if (!ref.mounted) return;
    if (r.questions.isEmpty) {
      final err = (r.error != null && r.error!.isNotEmpty) ? r.error! : null;
      state = state.copyWith(busy: false, error: () => err);
      ref.read(askControllerProvider.notifier).pushAiMessage(
            '出题失败${err != null ? '（$err）' : ''}，请稍后再试一次。',
            mode: 'quiz',
          );
      return;
    }
    state = ImmersiveQuizState(quizId: r.quizId, questions: r.questions, busy: false);
  }

  void pickAnswer(String questionId, int index) {
    if (state.submitted) return;
    state = state.copyWith(answers: {...state.answers, questionId: index});
  }

  Future<void> submit() async {
    final quizId = state.quizId;
    if (quizId == null || state.submitted || state.questions.isEmpty) return;
    if (state.answers.length < state.questions.length) return;
    state = state.copyWith(busy: true);
    try {
      final results = await ref.read(readAskCardsRepositoryProvider).submitQuiz(
            quizId: quizId,
            questions: state.questions,
            answers: state.answers,
          );
      if (!ref.mounted) return;
      state = state.copyWith(busy: false, submitted: true, results: results);
    } catch (_) {
      if (!ref.mounted) return;
      state = state.copyWith(busy: false, error: () => '提交失败，测验可能已过期');
    }
  }

  void clear() => state = const ImmersiveQuizState();
}

final immersiveQuizProvider = NotifierProvider<ImmersiveQuizController, ImmersiveQuizState>(ImmersiveQuizController.new);

class ImmersiveDiagnosticState {
  const ImmersiveDiagnosticState({
    this.questions = const [],
    this.replies = const {},
    this.intro = '',
    this.busy = false,
  });

  final List<DiagnosticQuestion> questions;
  final Map<String, String> replies;
  final String intro;
  final bool busy;

  bool get active => questions.isNotEmpty;

  ImmersiveDiagnosticState copyWith({
    List<DiagnosticQuestion>? questions,
    Map<String, String>? replies,
    String? intro,
    bool? busy,
  }) =>
      ImmersiveDiagnosticState(
        questions: questions ?? this.questions,
        replies: replies ?? this.replies,
        intro: intro ?? this.intro,
        busy: busy ?? this.busy,
      );
}

class ImmersiveDiagnosticController extends Notifier<ImmersiveDiagnosticState> {
  @override
  ImmersiveDiagnosticState build() {
    ref.listen<int?>(
      readerControllerProvider.select((s) => s.currentLesson?.id),
      (prev, next) {
        if (prev != next) state = const ImmersiveDiagnosticState();
      },
    );
    return const ImmersiveDiagnosticState();
  }

  Future<void> start() async {
    final ask = ref.read(askControllerProvider);
    final lessonId = ask.lessonId;
    if (lessonId == null || state.busy) return;
    final ctx = ask.selected.isNotEmpty ? ask.selected : ask.context;
    state = const ImmersiveDiagnosticState(busy: true);
    try {
      final r = await ref.read(readAskCardsRepositoryProvider).fetchDiagnosticQuestions(
            lessonId: lessonId,
            context: ctx,
          );
      if (!ref.mounted) return;
      if (r.questions.isEmpty) {
        state = const ImmersiveDiagnosticState();
        ref.read(askControllerProvider.notifier).pushAiMessage('提问失败，请确认已配置 AI');
        return;
      }
      state = ImmersiveDiagnosticState(questions: r.questions, intro: r.intro);
    } catch (_) {
      if (!ref.mounted) return;
      state = const ImmersiveDiagnosticState();
      ref.read(askControllerProvider.notifier).pushAiMessage('提问失败，请确认已配置 AI');
    }
  }

  void pickReply(String questionId, String value) {
    state = state.copyWith(replies: {...state.replies, questionId: value});
  }

  Future<void> submit() async {
    final askCtl = ref.read(askControllerProvider.notifier);
    final ask = ref.read(askControllerProvider);
    final lessonId = ask.lessonId;
    if (lessonId == null || state.questions.isEmpty) return;
    for (final q in state.questions) {
      if ((state.replies[q.id] ?? '').trim().isEmpty) return;
    }
    state = state.copyWith(busy: true);
    await askCtl.submitDiagnosticReplies(
      lessonId: lessonId,
      context: ask.selected.isNotEmpty ? ask.selected : ask.context,
      replies: state.replies,
    );
    if (!ref.mounted) return;
    state = const ImmersiveDiagnosticState();
  }
}

final immersiveDiagnosticProvider =
    NotifierProvider<ImmersiveDiagnosticController, ImmersiveDiagnosticState>(ImmersiveDiagnosticController.new);
