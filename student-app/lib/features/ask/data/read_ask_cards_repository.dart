import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'read_ask_cards_models.dart';

class ReadAskCardsRepository {
  ReadAskCardsRepository(this._api);

  final ApiClient _api;

  Future<({int? quizId, List<ReaderQuizQuestion> questions, String? error})> generateQuiz({
    required int lessonId,
  }) async {
    try {
      final raw = await _api.post('/api/quiz/generate', body: {'lesson_id': lessonId});
      final m = asMap(raw);
      final qs = m['questions'];
      final questions = <ReaderQuizQuestion>[];
      if (qs is List) {
        for (final q in qs) {
          final parsed = ReaderQuizQuestion.tryParse(q);
          if (parsed != null) questions.add(parsed);
        }
      }
      final quizId = m['quiz_id'] is num ? (m['quiz_id'] as num).toInt() : null;
      return (quizId: quizId, questions: questions, error: questions.isEmpty ? '${m['detail'] ?? ''}' : null);
    } on ApiException catch (e) {
      return (quizId: null, questions: const <ReaderQuizQuestion>[], error: e.message);
    }
  }

  Future<List<ReaderQuizGradeRow>> submitQuiz({
    required int quizId,
    required List<ReaderQuizQuestion> questions,
    required Map<String, int> answers,
  }) async {
    final payload = [
      for (final q in questions)
        {
          'question_id': q.id,
          'selected_index': answers[q.id],
        },
    ];
    final raw = await _api.post('/api/quiz/submit', body: {'quiz_id': quizId, 'answers': payload});
    final m = asMap(raw);
    final rows = m['answers'];
    if (rows is! List) return const [];
    return [for (final r in rows) ReaderQuizGradeRow.tryParse(r)].whereType<ReaderQuizGradeRow>().toList();
  }

  Future<({List<DiagnosticQuestion> questions, String intro})> fetchDiagnosticQuestions({
    required int lessonId,
    required String context,
  }) async {
    final raw = await _api.post('/api/ask/questions', body: {'lesson_id': lessonId, 'context': context});
    final m = asMap(raw);
    final qs = m['questions'];
    final questions = <DiagnosticQuestion>[];
    if (qs is List) {
      for (final q in qs) {
        final parsed = DiagnosticQuestion.tryParse(q);
        if (parsed != null) questions.add(parsed);
      }
    }
    return (questions: questions, intro: '${m['intro'] ?? ''}');
  }

  Future<({String answer, List<int> citations})> askReply({
    required int lessonId,
    required String context,
    required Map<String, String> replies,
  }) async {
    final raw = await _api.post('/api/ask/reply', body: {
      'lesson_id': lessonId,
      'context': context,
      'replies': replies,
    });
    final m = asMap(raw);
    final c = m['citations'];
    final citations = c is List ? c.whereType<num>().map((n) => n.toInt()).toList() : <int>[];
    return (answer: '${m['answer'] ?? ''}', citations: citations);
  }
}

final readAskCardsRepositoryProvider =
    Provider<ReadAskCardsRepository>((ref) => ReadAskCardsRepository(ref.watch(apiClientProvider)));
