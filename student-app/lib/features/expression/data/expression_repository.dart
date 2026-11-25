import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

class ExpressionTopic {
  const ExpressionTopic({
    required this.kind,
    required this.id,
    required this.title,
  });

  final String kind;
  final int id;
  final String title;

  static ExpressionTopic? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final map = Map<String, dynamic>.from(raw);
    final kind = map['kind'];
    final id = map['id'];
    final title = map['title'];
    if ((kind != 'knowledge_point' && kind != 'training_item') ||
        id is! num ||
        title is! String) {
      return null;
    }
    return ExpressionTopic(kind: kind as String, id: id.toInt(), title: title);
  }
}

class ExpressionRepository {
  ExpressionRepository(this._api);

  final ApiClient _api;

  Future<List<ExpressionTopic>> topics({required int userId}) async {
    final response = asMap(
      await _api.get('/api/expression/topics', query: {'user_id': userId}),
    );
    final rawTopics = response['topics'];
    if (rawTopics is! List) return const [];
    return rawTopics
        .map(ExpressionTopic.tryParse)
        .whereType<ExpressionTopic>()
        .toList();
  }

  Future<void> createNote({
    required int userId,
    int? knowledgePointId,
    int? itemId,
    required String text,
  }) async {
    assertExpressionNoteTarget(
      knowledgePointId: knowledgePointId,
      itemId: itemId,
    );
    final body = <String, dynamic>{'user_id': userId, 'text': text};
    if (knowledgePointId != null) body['knowledge_point_id'] = knowledgePointId;
    if (itemId != null) body['item_id'] = itemId;
    await _api.post('/api/expression/notes', body: body);
  }
}

/// [createNote] 必须且只能指定 knowledge_point 或 training_item 之一。
void assertExpressionNoteTarget({
  int? knowledgePointId,
  int? itemId,
}) {
  final hasKp = knowledgePointId != null;
  final hasItem = itemId != null;
  if (hasKp == hasItem) {
    throw ArgumentError(
      'createNote requires exactly one of knowledgePointId or itemId '
      '(got knowledgePointId=$knowledgePointId, itemId=$itemId)',
    );
  }
}

final expressionRepositoryProvider = Provider<ExpressionRepository>(
  (ref) => ExpressionRepository(ref.watch(apiClientProvider)),
);
