import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 知识点（来自任务 content 的 JSON）
class KnowledgePoint {
  const KnowledgePoint({
    required this.id,
    required this.content,
    required this.category,
    required this.question,
    required this.answer,
  });

  factory KnowledgePoint.fromJson(Map<String, dynamic> j) => KnowledgePoint(
        id: (j['id'] as num?)?.toInt() ?? 0,
        content: '${j['content'] ?? ''}',
        category: '${j['category'] ?? ''}',
        question: '${j['question'] ?? ''}',
        answer: '${j['answer'] ?? ''}',
      );

  final int id;
  final String content;
  final String category;
  final String question;
  final String answer;

  /// 题干：AI 出的问题优先，否则直接展示知识点内容
  String get display => question.isNotEmpty ? question : content;
}

List<KnowledgePoint> parseKnowledgeContent(String content) {
  if (content.isEmpty) return const [];
  try {
    final list = jsonDecode(content);
    if (list is! List) return const [];
    return [for (final p in list.whereType<Map>()) KnowledgePoint.fromJson(Map<String, dynamic>.from(p))];
  } catch (_) {
    return const [];
  }
}

/// 单题判分结果
class KnowledgeResultItem {
  const KnowledgeResultItem({required this.id, required this.isCorrect, required this.answer});

  final int id;
  final bool isCorrect;
  final String answer;
}

class KnowledgeGradeResult {
  const KnowledgeGradeResult({required this.correct, required this.total, required this.items});

  final int correct;
  final int total;
  final List<KnowledgeResultItem> items;

  factory KnowledgeGradeResult.fromJson(Map<String, dynamic> j) => KnowledgeGradeResult(
        correct: (j['correct'] as num?)?.toInt() ?? 0,
        total: (j['total'] as num?)?.toInt() ?? 0,
        items: [
          if (j['results'] is List)
            for (final r in (j['results'] as List).whereType<Map>())
              KnowledgeResultItem(
                id: (r['id'] as num?)?.toInt() ?? 0,
                isCorrect: r['is_correct'] == true,
                answer: '${r['answer'] ?? ''}',
              ),
        ],
      );
}

class KnowledgeRepository {
  KnowledgeRepository(this._api);

  final ApiClient _api;

  Future<KnowledgeGradeResult> grade({
    required int userId,
    required int taskId,
    required List<Map<String, dynamic>> answers,
  }) async {
    final r = asMap(await _api.post('/api/tasks/$taskId/knowledge-review', body: {
      'user_id': userId,
      'answers': answers,
    }));
    return KnowledgeGradeResult.fromJson(r);
  }
}

final knowledgeRepositoryProvider = Provider<KnowledgeRepository>((ref) => KnowledgeRepository(ref.watch(apiClientProvider)));
