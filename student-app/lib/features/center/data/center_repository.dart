import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'center_models.dart';

class CenterRepository {
  CenterRepository(this._api);

  final ApiClient _api;

  Future<CenterMaterial> listening(int userId) async =>
      CenterMaterial.fromJson(asMap(await _api.get('/api/listening/material', query: {'user_id': userId})));

  /// 阅读取语文快照的当前课；没有当前课时返回空材料
  Future<CenterMaterial> reading(int userId) async {
    final snap = asMap(await _api.get('/api/home/snapshot', query: {'user_id': userId, 'subject': '语文'}));
    final lp = snap['lesson_progress'];
    final lessonId = lp is Map && lp['current_lesson_id'] is num ? (lp['current_lesson_id'] as num).toInt() : null;
    if (lessonId == null) return CenterMaterial.empty;
    return CenterMaterial.fromJson(
      asMap(await _api.get('/api/reading/material', query: {'lesson_id': lessonId})),
      lessonId: lessonId,
    );
  }

  Future<void> submitWrong({
    required int userId,
    required String question,
    required String yourAnswer,
    required String correctAnswer,
    required String sourceType,
  }) async {
    await _api.post('/api/review/submit', body: {
      'user_id': userId,
      'question': question,
      'your_answer': yourAnswer,
      'correct_answer': correctAnswer,
      'source_type': sourceType,
    });
  }
}

final centerRepositoryProvider = Provider<CenterRepository>((ref) => CenterRepository(ref.watch(apiClientProvider)));
