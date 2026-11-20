import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/ui/sudoku_page.dart';

import 'brain_game_test_helpers.dart';

/// 数独必须画得出每一格的边线，否则「看不出有格」。
void main() {
  testWidgets('棋盘包含格线绘制层（细线 + 宫线）', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest());

    final grid = find.byKey(const ValueKey('sudoku-grid'));
    expect(grid, findsOneWidget);

    // 棋盘内必须存在一个 CustomPaint 画格线
    final painters = find.descendant(
      of: grid,
      matching: find.byType(CustomPaint),
    );
    expect(painters, findsWidgets);
  });

  testWidgets('6×6 中等难度棋盘同样是正方形且不溢出', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest());
    await tester.tap(find.text('中等'));
    await tester.pumpAndSettle();

    final size = tester.getSize(find.byKey(const ValueKey('sudoku-grid')));
    expect(size.width, closeTo(size.height, 1.0));
    expect(tester.takeException(), isNull);
  });

  testWidgets('数独页渲染不抛异常（防止编码/绘制回归）', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest());
    expect(tester.takeException(), isNull);
    expect(find.byType(SudokuPage), findsOneWidget);
  });
}
