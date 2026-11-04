import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 一条对话消息
class AskMessage {
  const AskMessage({required this.role, required this.text, this.citations = const [], this.mode});

  final String role; // 'user' | 'ai'
  final String text;
  final List<int> citations;
  final String? mode;
}

/// SSE 流事件：stage | tool_call | tool_result | final | error
class AskStreamEvent {
  const AskStreamEvent(this.type, this.data);

  final String type;
  final Map<String, dynamic> data;
}

class AskRepository {
  AskRepository(this._api);

  final ApiClient _api;

  /// 调 /api/ask/stream，逐条吐出事件。
  Stream<AskStreamEvent> askStream({
    required int lessonId,
    required String question,
    required String context,
    required String mode,
    required List<String> sentences,
  }) async* {
    final stream = await _api.postStream('/api/ask/stream', body: {
      'lesson_id': lessonId,
      'question': question,
      'context': context,
      'mode': mode,
      'sentences': sentences,
    });

    final buffer = StringBuffer();
    await for (final chunk in stream) {
      buffer.write(utf8.decode(chunk));
      var text = buffer.toString();
      buffer.clear();
      int idx;
      while ((idx = text.indexOf('\n\n')) >= 0) {
        final block = text.substring(0, idx);
        text = text.substring(idx + 2);
        final event = _parseBlock(block);
        if (event != null) yield event;
      }
      if (text.isNotEmpty) buffer.write(text);
    }
    if (buffer.isNotEmpty) {
      final event = _parseBlock(buffer.toString());
      if (event != null) yield event;
    }
  }

  AskStreamEvent? _parseBlock(String block) {
    for (final line in block.split('\n')) {
      if (line.startsWith('data:')) {
        final jsonStr = line.substring(5).trim();
        if (jsonStr.isEmpty) continue;
        try {
          final obj = jsonDecode(jsonStr) as Map<String, dynamic>;
          final type = '${obj['type'] ?? ''}';
          final data = obj['data'];
          return AskStreamEvent(type, data is Map ? Map<String, dynamic>.from(data) : const {});
        } catch (_) {
          return null;
        }
      }
    }
    return null;
  }
}

final askRepositoryProvider = Provider<AskRepository>((ref) => AskRepository(ref.watch(apiClientProvider)));
