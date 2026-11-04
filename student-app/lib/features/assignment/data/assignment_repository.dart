import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'assignment_models.dart';

class AssignmentRepository {
  AssignmentRepository(this._api);

  final ApiClient _api;

  Future<List<AssignmentQuestion>> generate({
    required int userId,
    required int lessonId,
    required String subject,
    required List<String> previousQuestions,
    required List<String> wrongQuestions,
  }) async =>
      parseQuestions(await _api.post('/api/learning/assignment', body: {
        'user_id': userId,
        'lesson_id': lessonId,
        'subject': subject,
        'previous_questions': previousQuestions,
        'wrong_questions': wrongQuestions,
      }));

  Future<AssignmentResult> grade({
    required int userId,
    required int lessonId,
    required String subject,
    required List<Map<String, dynamic>> items,
  }) async =>
      AssignmentResult.fromJson(asMap(await _api.post('/api/learning/assignment/grade', body: {
        'user_id': userId,
        'lesson_id': lessonId,
        'subject': subject,
        'items': items,
      })));
}

final assignmentRepositoryProvider = Provider<AssignmentRepository>((ref) => AssignmentRepository(ref.watch(apiClientProvider)));
