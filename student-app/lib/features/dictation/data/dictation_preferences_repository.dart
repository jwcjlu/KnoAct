import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'dictation_input_mode.dart';

class DictationPreferencesRepository {
  DictationPreferencesRepository(this._api);

  final ApiClient _api;

  Future<DictationInputMode> fetch(int userId) async {
    final r = asMap(await _api.get('/api/learning/preferences', query: {'user_id': userId}));
    final raw = '${r['dictation_input_mode'] ?? ''}';
    return DictationInputMode.fromApi(raw);
  }
}

final dictationPreferencesRepositoryProvider =
    Provider<DictationPreferencesRepository>((ref) => DictationPreferencesRepository(ref.watch(apiClientProvider)));
