import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'data/bank_models.dart';
import 'data/bank_repository.dart';

final practiceBanksProvider = FutureProvider.autoDispose<List<PracticeBank>>((ref) {
  return ref.watch(bankRepositoryProvider).listPracticeBanks();
});
