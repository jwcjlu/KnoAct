import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'brain_game_models.dart';

class BrainGameRepository {
  BrainGameRepository(this._api);

  final ApiClient _api;

  /// 提交一局成绩。`solved=false`（扫雷踩雷）也提交，用于 played 统计。
  Future<({bool ok, bool isBest})> postResult({
    required int userId,
    required BrainGameKind kind,
    required BrainGameDifficulty difficulty,
    required int durationMs,
    required int moves,
    required bool solved,
  }) async {
    final d = asMap(
      await _api.post(
        '/api/brain-games/result',
        body: {
          'user_id': userId,
          'game': kind.id,
          'difficulty': difficulty.id,
          'duration_ms': durationMs,
          'moves': moves,
          'solved': solved,
        },
      ),
    );
    return (ok: d['ok'] == true, isBest: d['is_best'] == true);
  }

  /// 拉成绩统计；失败时返回空映射（游戏本身不受影响）。
  Future<BrainGameStats> stats({required int userId, int? bucketId}) async {
    try {
      final raw = asMap(
        await _api.get(
          '/api/brain-games/stats',
          query: {'user_id': userId, 'bucket_id': ?bucketId},
        ),
      );
      final out = <BrainGameKind, Map<BrainGameDifficulty, DifficultyStat>>{};
      for (final kind in BrainGameKind.values) {
        final perKind = raw[kind.id];
        if (perKind is! Map) continue;
        final m = <BrainGameDifficulty, DifficultyStat>{};
        for (final diff in BrainGameDifficulty.values) {
          final v = perKind[diff.id];
          if (v is Map) {
            m[diff] = DifficultyStat.fromJson(Map<String, dynamic>.from(v));
          }
        }
        out[kind] = m;
      }
      return out;
    } catch (_) {
      return const {};
    }
  }
}

final brainGameRepositoryProvider = Provider<BrainGameRepository>(
  (ref) => BrainGameRepository(ref.watch(apiClientProvider)),
);
