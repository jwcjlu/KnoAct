import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/dictation_input_mode.dart';
import 'data/dictation_preferences_repository.dart';

final dictationInputModeProvider = FutureProvider.autoDispose<DictationInputMode>((ref) async {
  final uid = ref.watch(currentChildIdProvider);
  if (uid == null) return DictationInputMode.paperPhoto;
  try {
    return await ref.read(dictationPreferencesRepositoryProvider).fetch(uid);
  } catch (_) {
    return DictationInputMode.paperPhoto;
  }
});
