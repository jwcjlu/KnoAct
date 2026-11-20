import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

String _faceAssetOf(WidgetTester tester) {
  final img = tester.widget<Image>(find.byKey(const ValueKey('mine-face')));
  return (img.image as AssetImage).assetName;
}

void main() {
  testWidgets('扫雷页首点前不布雷，显示开始提示', (tester) async {
    final repo = await pumpBrainGame(tester, minesweeperPageForTest());

    expect(find.text('数字扫雷'), findsOneWidget);
    expect(find.byKey(const ValueKey('minesweeper-board')), findsOneWidget);
    expect(find.textContaining('点一格开始'), findsOneWidget);
    expect(repo.statsCalls, 1);
  });

  testWidgets('首点后显示剩余雷数（说明首点安全未踩雷）', (tester) async {
    await pumpBrainGame(tester, minesweeperPageForTest());

    await tester.tap(find.byKey(const ValueKey('mine-cell-0')).first);
    await tester.pumpAndSettle();

    expect(find.textContaining('剩余'), findsOneWidget);
  });

  testWidgets('进行中显示 smile 表情', (tester) async {
    await pumpBrainGame(tester, minesweeperPageForTest());
    expect(_faceAssetOf(tester), 'assets/brain_games/smile.png');
  });

  testWidgets('三张表情与雷/旗图标都已打包成资源', (tester) async {
    for (final path in [
      'assets/brain_games/smile.png',
      'assets/brain_games/lose.png',
      'assets/brain_games/win.png',
      'assets/brain_games/flag.png',
      'assets/brain_games/mine.png',
    ]) {
      final data = await rootBundle.load(path);
      expect(data.lengthInBytes, greaterThan(500), reason: '$path 资源缺失');
    }
  });
}
