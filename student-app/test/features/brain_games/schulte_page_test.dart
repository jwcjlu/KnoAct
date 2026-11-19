import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

void main() {
  testWidgets('舒尔特页显示方格与下一个目标', (tester) async {
    final repo = await pumpBrainGame(tester, schultePageForTest());

    expect(find.text('舒尔特方格'), findsOneWidget);
    expect(find.byKey(const ValueKey('schulte-board')), findsOneWidget);
    expect(find.textContaining('下一个：1'), findsOneWidget);
    expect(repo.statsCalls, 1);
  });

  testWidgets('点错会累加错误数，点对推进目标', (tester) async {
    await pumpBrainGame(tester, schultePageForTest());

    // 点一个不是 1 的格子 → 错误 +1
    final notOne = find.byWidgetPredicate(
      (w) =>
          w is Text &&
          w.data != null &&
          w.data != '1' &&
          int.tryParse(w.data!) != null,
    );
    await tester.tap(notOne.first);
    await tester.pump();
    expect(find.textContaining('错误 1'), findsOneWidget);

    // 点 1 → 目标推进到 2
    await tester.tap(find.text('1').first);
    await tester.pump();
    expect(find.textContaining('下一个：2'), findsOneWidget);
  });
}
