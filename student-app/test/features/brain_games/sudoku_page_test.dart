import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

void main() {
  testWidgets('数独页显示棋盘与数字条', (tester) async {
    final repo = await pumpBrainGame(tester, sudokuPageForTest());

    expect(find.text('数独'), findsOneWidget);
    expect(find.text('简单'), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-grid')), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-pad-1')), findsOneWidget);
    expect(repo.statsCalls, 1);
  });

  testWidgets('切难度会重新生成棋盘（出现 6 的数字键）', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest());

    await tester.tap(find.text('中等'));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('sudoku-pad-6')), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-pad-7')), findsNothing);
  });
}
