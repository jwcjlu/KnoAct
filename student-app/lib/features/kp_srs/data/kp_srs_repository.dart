import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 自评取值（与后端 `knowledge_review.RESULTS` 一致）
const kpResultRemember = 'remember';
const kpResultFuzzy = 'fuzzy';
const kpResultForgot = 'forgot';

/// 到期项的出题方式：`reuse` / `generated` 带题目；`self_rate` 纯自评
class KpSrsPrompt {
  const KpSrsPrompt({
    this.source = 'self_rate',
    this.questionId,
    this.question,
    this.qtype,
  });

  factory KpSrsPrompt.fromJson(Object? raw) {
    if (raw is! Map) return const KpSrsPrompt();
    final qid = raw['question_id'];
    final q = raw['question'];
    final hasQuestion = qid is num && q is String && q.trim().isNotEmpty;
    return KpSrsPrompt(
      source: '${raw['source'] ?? 'self_rate'}',
      // 题目缺失一律退化为自评，避免页面出现「有 question_id 却无题干」
      questionId: hasQuestion ? qid.toInt() : null,
      question: hasQuestion ? q.trim() : null,
      qtype: raw['qtype'] is String ? raw['qtype'] as String : null,
    );
  }

  final String source;
  final int? questionId;
  final String? question;
  final String? qtype;

  bool get hasQuestion => questionId != null && (question ?? '').isNotEmpty;
}

/// 一个到期的知识点复习项
class KpSrsItem {
  const KpSrsItem({
    required this.itemId,
    required this.knowledgePointId,
    required this.title,
    required this.content,
    this.lessonTitle = '',
    this.prompt = const KpSrsPrompt(),
  });

  factory KpSrsItem.fromJson(Map<String, dynamic> j) => KpSrsItem(
        itemId: (j['item_id'] as num?)?.toInt() ?? 0,
        knowledgePointId: (j['knowledge_point_id'] as num?)?.toInt() ?? 0,
        title: '${j['title'] ?? ''}',
        content: '${j['content'] ?? ''}',
        lessonTitle: '${j['lesson_title'] ?? ''}',
        prompt: KpSrsPrompt.fromJson(j['prompt']),
      );

  final int itemId;
  final int knowledgePointId;
  final String title;
  final String content;
  final String lessonTitle;
  final KpSrsPrompt prompt;
}

List<KpSrsItem> _itemsFromList(Object? raw) {
  if (raw is! List) return const [];
  return [
    for (final e in raw.whereType<Map>())
      if (((e['item_id'] as num?)?.toInt() ?? 0) > 0) KpSrsItem.fromJson(Map<String, dynamic>.from(e)),
  ];
}

/// 解析 kp_review 任务 content（JSON 数组快照）；异常/格式不符返回空列表
List<KpSrsItem> parseKpSrsContent(String content) {
  if (content.isEmpty) return const [];
  try {
    return _itemsFromList(jsonDecode(content));
  } catch (_) {
    return const [];
  }
}

/// `POST /api/knowledge-review/complete` 的响应
class KpSrsCompleteResult {
  const KpSrsCompleteResult({
    required this.result,
    this.isCorrect,
    this.graded = false,
    this.alreadyCompleted = false,
    this.intervalIndex,
    this.nextReviewAt,
  });

  factory KpSrsCompleteResult.fromJson(Map<String, dynamic> j) => KpSrsCompleteResult(
        result: '${j['result'] ?? ''}',
        isCorrect: j['is_correct'] is bool ? j['is_correct'] as bool : null,
        graded: j['graded'] == true,
        alreadyCompleted: j['already_completed'] == true,
        intervalIndex: (j['interval_index'] as num?)?.toInt(),
        nextReviewAt: j['next_review_at'] as String?,
      );

  /// 服务端最终采用的结果（带题时由判分覆盖自评）
  final String result;
  final bool? isCorrect;
  final bool graded;
  final bool alreadyCompleted;
  final int? intervalIndex;
  final String? nextReviewAt;
}

class KpSrsRepository {
  KpSrsRepository(this._api);

  final ApiClient _api;

  Future<List<KpSrsItem>> fetchDue({required int userId, String? subject}) async {
    final r = asMap(await _api.get('/api/knowledge-review/due', query: {
      'user_id': userId,
      if (subject != null && subject.isNotEmpty) 'subject': subject,
    }));
    return _itemsFromList(r['items']);
  }

  Future<KpSrsCompleteResult> complete({
    required int userId,
    required int itemId,
    required String result,
    int? questionId,
    String? studentAnswer,
    int? durationMs,
  }) async {
    final r = asMap(await _api.post('/api/knowledge-review/complete', body: {
      'user_id': userId,
      'item_id': itemId,
      'result': result,
      'question_id': ?questionId,
      'student_answer': ?studentAnswer,
      'duration_ms': ?durationMs,
    }));
    return KpSrsCompleteResult.fromJson(r);
  }
}

final kpSrsRepositoryProvider = Provider<KpSrsRepository>((ref) => KpSrsRepository(ref.watch(apiClientProvider)));
