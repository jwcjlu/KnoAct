import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/brain_games/data/brain_game_models.dart';
import 'package:student_app/features/brain_games/data/brain_game_repository.dart';

class FakeApi implements ApiClient {
  FakeApi({this.statsJson = const {}});

  final Map<String, dynamic> statsJson;
  final posts = <({String path, Object? body})>[];

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    posts.add((path: path, body: body));
    return {'ok': true, 'is_best': true};
  }

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    if (path == '/api/brain-games/stats') return statsJson;
    throw ApiException('unexpected path $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('Difficulty 的 id 与中文标签', () {
    expect(BrainGameDifficulty.easy.id, 'easy');
    expect(BrainGameDifficulty.medium.label, '中等');
    expect(BrainGameDifficulty.values.length, 3);
  });

  test('GameKind 的 id 与接口路径片段一致', () {
    expect(BrainGameKind.sudoku.id, 'sudoku');
    expect(BrainGameKind.schulte.id, 'schulte');
    expect(BrainGameKind.minesweeper.id, 'minesweeper');
    expect(GameKindRoute.pathOf(BrainGameKind.sudoku), '/brain-games/sudoku');
  });

  test('提交成绩会打 /api/brain-games/result 并回传 isBest', () async {
    final api = FakeApi();
    final repo = BrainGameRepository(api);
    final r = await repo.postResult(
      userId: 11,
      kind: BrainGameKind.sudoku,
      difficulty: BrainGameDifficulty.easy,
      durationMs: 82000,
      moves: 30,
      solved: true,
    );
    expect(r.isBest, isTrue);
    expect(api.posts.single.path, '/api/brain-games/result');
    final body = api.posts.single.body as Map<String, dynamic>;
    expect(body['user_id'], 11);
    expect(body['game'], 'sudoku');
    expect(body['difficulty'], 'easy');
    expect(body['duration_ms'], 82000);
    expect(body['moves'], 30);
    expect(body['solved'], true);
  });

  test('解析 stats 为 DifficultyStat 映射', () async {
    final api = FakeApi(
      statsJson: {
        'sudoku': {
          'easy': {'best_ms': 82000, 'played': 3, 'solved': 2},
        },
        'schulte': <String, dynamic>{},
        'minesweeper': {
          'hard': {'best_ms': null, 'played': 1, 'solved': 0},
        },
      },
    );
    final repo = BrainGameRepository(api);
    final stats = await repo.stats(userId: 11);

    expect(
      stats[BrainGameKind.sudoku]![BrainGameDifficulty.easy]!.bestMs,
      82000,
    );
    expect(stats[BrainGameKind.sudoku]![BrainGameDifficulty.easy]!.played, 3);
    expect(stats[BrainGameKind.schulte], isEmpty);
    expect(
      stats[BrainGameKind.minesweeper]![BrainGameDifficulty.hard]!.bestMs,
      isNull,
    );
  });
}
