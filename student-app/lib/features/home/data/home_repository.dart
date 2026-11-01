import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'home_models.dart';

class HomeRepository {
  HomeRepository(this._api);

  final ApiClient _api;

  Future<HomeSnapshot> snapshot(int userId, String subject) async =>
      HomeSnapshot.fromJson(asMap(await _api.get('/api/home/snapshot', query: {'user_id': userId, 'subject': subject})));

  Future<List<StudyTask>> tasks(int userId, String date) async {
    final list = asList(await _api.get('/api/tasks', query: {'user_id': userId, 'date': date, 'role': 'child'}));
    return [for (final t in list) StudyTask.fromJson(asMap(t))];
  }

  Future<int> balance(int userId) async {
    final d = asMap(await _api.get('/api/points/balance', query: {'user_id': userId}));
    return (d['balance'] as num?)?.toInt() ?? 0;
  }

  /// 返回是否兑换成功（积分不足为 false）
  Future<bool> redeem(int userId, String device, int minutes) async {
    final d = asMap(await _api.post('/api/points/redeem', body: {'user_id': userId, 'device': device, 'minutes': minutes}));
    return d['success'] == true;
  }

  Future<void> submitTask(int taskId) async {
    await _api.post('/api/tasks/$taskId/submit');
  }
}

final homeRepositoryProvider = Provider<HomeRepository>((ref) => HomeRepository(ref.watch(apiClientProvider)));
