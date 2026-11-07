import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'math_models.dart';

class MathRepository {
  MathRepository(this._api);

  final ApiClient _api;

  Future<MathTaskMaterial> fetchMaterial(int taskId) async {
    final r = asMap(await _api.get('/api/math/task/$taskId/material'));
    if (r['ok'] != true) throw ApiException('${r['error'] ?? '加载数学题失败'}');
    return MathTaskMaterial.fromJson(r);
  }

  Future<MathGradeResult> gradeCalc({required int userId, required int taskId, required List<String> answers}) async {
    final r = asMap(await _api.post('/api/math/task/$taskId/grade', body: {
      'user_id': userId,
      'answers': answers,
    }));
    if (r['ok'] == false) throw ApiException('${r['error'] ?? '判分失败'}');
    return MathGradeResult.fromJson(r);
  }

  /// 应用题单题拍照；[wordIndex] 为题序（与 material `word[].index` 一致）。
  Future<MathWordItem> uploadWordPhoto(
    int taskId,
    int wordIndex,
    List<int> bytes, {
    String filename = 'math_word.jpg',
  }) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
      'word_index': wordIndex,
    });
    final r = asMap(await _api.postMultipart('/api/tasks/$taskId/upload-photo', form));
    if (r['ok'] != true) throw ApiException('${r['error'] ?? '上传照片失败'}');
    final grade = r['grade'] is Map ? Map<String, dynamic>.from(r['grade'] as Map) : <String, dynamic>{};
    return MathWordItem(
      index: (r['word_index'] as num?)?.toInt() ?? wordIndex,
      question: '',
      photoPath: r['path'] == null ? null : '${r['path']}',
      aiStatus: grade['ai_status'] == null ? null : '${grade['ai_status']}',
      parentStatus: 'none',
    );
  }
}

final mathRepositoryProvider = Provider<MathRepository>((ref) => MathRepository(ref.watch(apiClientProvider)));
