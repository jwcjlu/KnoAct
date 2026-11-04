import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 数学题（来自任务 content 的 JSON）
class MathQuestion {
  const MathQuestion({required this.question, required this.answer, this.yourAnswer = '', this.isCorrect});

  factory MathQuestion.fromJson(Map<String, dynamic> j) => MathQuestion(
        question: '${j['question'] ?? ''}',
        answer: '${j['answer'] ?? ''}',
        yourAnswer: '${j['your_answer'] ?? ''}',
        isCorrect: j['is_correct'] is bool ? j['is_correct'] as bool : null,
      );

  final String question;
  final String answer;
  final String yourAnswer;
  final bool? isCorrect;
}

/// 解析任务 content（JSON 字符串）为数学题列表
List<MathQuestion> parseMathContent(String content) {
  if (content.isEmpty) return const [];
  try {
    final list = jsonDecode(content);
    if (list is! List) return const [];
    return [for (final q in list.whereType<Map>()) MathQuestion.fromJson(Map<String, dynamic>.from(q))];
  } catch (_) {
    return const [];
  }
}

class MathGradeResult {
  const MathGradeResult({required this.correct, required this.total, required this.results});

  final int correct;
  final int total;
  final List<bool> results;

  factory MathGradeResult.fromJson(Map<String, dynamic> j) => MathGradeResult(
        correct: (j['correct'] as num?)?.toInt() ?? 0,
        total: (j['total'] as num?)?.toInt() ?? 0,
        results: [
          if (j['results'] is List)
            for (final r in (j['results'] as List).whereType<Map>()) r['is_correct'] == true,
        ],
      );
}

class MathRepository {
  MathRepository(this._api);

  final ApiClient _api;

  Future<MathGradeResult> grade({required int userId, required int taskId, required List<String> answers}) async {
    final r = asMap(await _api.post('/api/math/task/$taskId/grade', body: {
      'user_id': userId,
      'answers': answers,
    }));
    return MathGradeResult.fromJson(r);
  }
}

final mathRepositoryProvider = Provider<MathRepository>((ref) => MathRepository(ref.watch(apiClientProvider)));
