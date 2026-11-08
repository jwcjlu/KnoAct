import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'bank_models.dart';

abstract class BankRepository {
  Future<List<PracticeBank>> listPracticeBanks();
  Future<List<BankQuestion>> fetchQuestions(int bankId, {List<int>? questionIds});
  Future<BankSubmitResult> submit({required int bankId, required List<Map<String, dynamic>> answers});
}

class ApiBankRepository implements BankRepository {
  ApiBankRepository(this._api);

  final ApiClient _api;

  @override
  Future<List<PracticeBank>> listPracticeBanks() async {
    final data = await _api.get('/api/banks/practice');
    return asList(data).map((e) => PracticeBank.fromJson(asMap(e))).toList();
  }

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId, {List<int>? questionIds}) async {
    final query = questionIds != null && questionIds.isNotEmpty
        ? {'ids': questionIds.join(',')}
        : null;
    final data = await _api.get('/api/banks/$bankId/questions', query: query);
    final list = asList(data);
    return list.map((e) => BankQuestion.fromJson(asMap(e))).toList();
  }

  @override
  Future<BankSubmitResult> submit({required int bankId, required List<Map<String, dynamic>> answers}) async {
    final data = await _api.post('/api/banks/submit', body: {'bank_id': bankId, 'answers': answers});
    return BankSubmitResult.fromJson(asMap(data));
  }
}

final bankRepositoryProvider = Provider<BankRepository>((ref) {
  return ApiBankRepository(ref.watch(apiClientProvider));
});
