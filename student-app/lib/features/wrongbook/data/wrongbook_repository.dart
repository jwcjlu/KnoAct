import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'wrongbook_models.dart';

class WrongbookRepository {
  WrongbookRepository(this._api);

  final ApiClient _api;

  Future<List<MistakeItem>> list(int userId, {String subject = ''}) async =>
      parseMistakes(await _api.get('/api/mistakes', query: {'user_id': userId, if (subject.isNotEmpty && subject != '全部') 'subject': subject}));

  Future<void> markCorrect(int id) => _api.post('/api/mistakes/$id/correct');

  Future<void> markWrong(int id) => _api.post('/api/mistakes/$id/wrong');
}

final wrongbookRepositoryProvider = Provider<WrongbookRepository>((ref) => WrongbookRepository(ref.watch(apiClientProvider)));
