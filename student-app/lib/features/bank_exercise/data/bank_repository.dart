import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'bank_models.dart';

abstract class BankRepository {
  Future<List<PracticeBank>> listPracticeBanks();
  Future<List<BankQuestion>> fetchQuestions(int bankId,
      {List<int>? questionIds, List<int>? extraBankIds});
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
  Future<List<BankQuestion>> fetchQuestions(int bankId,
      {List<int>? questionIds, List<int>? extraBankIds}) async {
    final q = <String, String>{};
    if (questionIds != null && questionIds.isNotEmpty) {
      q['ids'] = questionIds.join(',');
    }
    if (extraBankIds != null && extraBankIds.isNotEmpty) {
      q['extra_bank_ids'] = extraBankIds.join(',');
    }
    final data = await _api.get('/api/banks/$bankId/questions',
        query: q.isEmpty ? null : q);
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
