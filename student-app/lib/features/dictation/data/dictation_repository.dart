import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 听写词条
class DictWord {
  const DictWord({required this.id, required this.word, required this.extra});

  factory DictWord.fromJson(Map<String, dynamic> j) => DictWord(
        id: (j['id'] as num?)?.toInt() ?? 0,
        word: '${j['word'] ?? ''}',
        extra: '${j['extra'] ?? ''}',
      );

  final int id;
  final String word;
  final String extra;

  /// 拼音（extra 空格分隔的第一段）
  String get pinyin => extra.split(RegExp(r'\s+')).firstOrNull ?? '';

  /// 释义（extra 除拼音外的部分）
  String get meaning {
    final parts = extra.split(RegExp(r'\s+'));
    return parts.length > 1 ? parts.sublist(1).join(' ') : extra;
  }
}

/// 解析任务 content（JSON 字符串）为听写词条列表
List<DictWord> parseDictContent(String content) {
  if (content.isEmpty) return const [];
  try {
    final list = jsonDecode(content);
    if (list is! List) return const [];
    return [for (final w in list.whereType<Map>()) DictWord.fromJson(Map<String, dynamic>.from(w))];
  } catch (_) {
    return const [];
  }
}

/// 手写批改单题结果
class DictGradeItem {
  const DictGradeItem({required this.index, required this.isCorrect, required this.written});

  final int index;
  final bool isCorrect;
  final String written;
}

class DictRepository {
  DictRepository(this._api);

  final ApiClient _api;

  Future<List<DictWord>> words(int userId, String subject) async {
    final list = await _api.get('/api/dictation/words', query: {'user_id': userId, 'subject': subject});
    return [for (final w in (list as List).whereType<Map>()) DictWord.fromJson(Map<String, dynamic>.from(w))];
  }

  /// 手写批改：words 是 [{index, word}]，返回 results [{index, is_correct, written}]
  Future<List<DictGradeItem>> gradeHandwriting({
    required int userId,
    required List<Map<String, dynamic>> words,
    required String imageBase64,
  }) async {
    final r = asMap(await _api.post('/api/dictation/grade-handwriting', body: {
      'user_id': userId,
      'words': words,
      'image_base64': imageBase64,
    }));
    final results = r['results'];
    if (results is! List) return const [];
    return [
      for (final item in results.whereType<Map>())
        DictGradeItem(
          index: (item['index'] as num?)?.toInt() ?? 0,
          isCorrect: item['is_correct'] == true,
          written: '${item['written'] ?? ''}',
        ),
    ];
  }

  Future<void> complete({
    required int userId,
    required int correct,
    required int wrong,
    required List<Map<String, dynamic>> wrongWords,
  }) async {
    await _api.post('/api/dictation/complete', body: {
      'user_id': userId,
      'correct': correct,
      'wrong': wrong,
      'wrong_words': wrongWords,
    });
  }

  Future<void> appeal({required int userId, required String word, required int wordId}) async {
    await _api.post('/api/dictation/appeal', body: {'user_id': userId, 'word': word, 'word_id': wordId, 'reason': '批改可能有误'});
  }
}

final dictationRepositoryProvider = Provider<DictRepository>((ref) => DictRepository(ref.watch(apiClientProvider)));
