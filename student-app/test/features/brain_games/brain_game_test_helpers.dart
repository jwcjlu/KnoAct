import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/brain_games/data/brain_game_models.dart';
import 'package:student_app/features/brain_games/data/brain_game_repository.dart';
import 'package:student_app/features/brain_games/ui/minesweeper_page.dart';
import 'package:student_app/features/brain_games/ui/schulte_page.dart';
import 'package:student_app/features/brain_games/ui/sudoku_page.dart';

import '../auth/session_test.dart' show FakeAuthRepository;

/// 假仓库：返回值类型必须与真实 `BrainGameRepository` 完全一致，
/// 否则 `implements` 直接编译失败（`noSuchMethod` 救不了返回类型不兼容）。
class FakeBrainGameRepo implements BrainGameRepository {
  FakeBrainGameRepo({this.statsResult = const {}, this.best = false});

  final BrainGameStats statsResult;
  final bool best;
  int statsCalls = 0;
  final results =
      <
        ({
          BrainGameKind kind,
          BrainGameDifficulty difficulty,
          int durationMs,
          int moves,
          bool solved,
        })
      >[];

  @override
  Future<BrainGameStats> stats({required int userId, int? bucketId}) async {
    statsCalls++;
    return statsResult;
  }

  @override
  Future<({bool ok, bool isBest})> postResult({
    required int userId,
    required BrainGameKind kind,
    required BrainGameDifficulty difficulty,
    required int durationMs,
    required int moves,
    required bool solved,
  }) async {
    results.add((
      kind: kind,
      difficulty: difficulty,
      durationMs: durationMs,
      moves: moves,
      solved: solved,
    ));
    return (ok: true, isBest: best);
  }
}

/// 灌好登录会话后渲染任意游戏页。
///
/// 必须注入会话：页面 `initState` 里读 `currentChildIdProvider` 拿用户 id，
/// 裸 `ProviderScope` 会让 `sessionProvider` 走真实存储（测试里抛异常 + 留 pending Timer）。
Future<FakeBrainGameRepo> pumpBrainGame(
  WidgetTester tester,
  Widget page, {
  FakeBrainGameRepo? repo,
  Size size = const Size(420, 900),
}) async {
  final r = repo ?? FakeBrainGameRepo();
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);

  final container = ProviderContainer(
    overrides: [
      brainGameRepositoryProvider.overrideWithValue(r),
      authRepositoryProvider.overrideWithValue(
        FakeAuthRepository(const Child(4, '金同学')),
      ),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(home: page),
    ),
  );
  await tester.pumpAndSettle();
  return r;
}

Widget sudokuPageForTest() => const SudokuPage();
Widget schultePageForTest() => const SchultePage();
Widget minesweeperPageForTest() => const MinesweeperPage();
