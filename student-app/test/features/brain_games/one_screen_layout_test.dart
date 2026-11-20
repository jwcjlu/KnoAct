import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

/// 小屏（iPhone SE 尺寸 320×568）下三个游戏都不该出现溢出或纵向滚动。
void main() {
  const small = Size(320, 568);

  testWidgets('数独：320×568 一屏放得下，无溢出', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest(), size: small);
    expect(tester.takeException(), isNull);
    expect(find.byKey(const ValueKey('sudoku-grid')), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-pad-1')), findsOneWidget);
  });

  testWidgets('舒尔特：320×568 一屏放得下，无溢出', (tester) async {
    await pumpBrainGame(tester, schultePageForTest(), size: small);
    expect(tester.takeException(), isNull);
    expect(find.byKey(const ValueKey('schulte-board')), findsOneWidget);
  });

  testWidgets('扫雷：320×568 一屏放得下，无溢出', (tester) async {
    await pumpBrainGame(tester, minesweeperPageForTest(), size: small);
    expect(tester.takeException(), isNull);
    expect(find.byKey(const ValueKey('minesweeper-board')), findsOneWidget);
  });

  testWidgets('数独：困难 9×9 在小屏也不溢出', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest(), size: small);
    await tester.tap(find.text('困难'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.byKey(const ValueKey('sudoku-pad-9')), findsOneWidget);
  });

  testWidgets('扫雷：困难 12×12 在小屏也不溢出', (tester) async {
    await pumpBrainGame(tester, minesweeperPageForTest(), size: small);
    await tester.tap(find.text('困难'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('舒尔特：困难 5×5 在小屏也不溢出', (tester) async {
    await pumpBrainGame(tester, schultePageForTest(), size: small);
    await tester.tap(find.text('困难'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
