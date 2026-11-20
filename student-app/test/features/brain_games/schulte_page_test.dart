import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

String _textOf(WidgetTester tester, String key) {
  final w = tester.widget<Text>(find.byKey(ValueKey(key)));
  return w.data ?? '';
}

void main() {
  testWidgets('舒尔特页一屏显示方格与下一个目标', (tester) async {
    final repo = await pumpBrainGame(tester, schultePageForTest());

    expect(find.text('舒尔特方格'), findsOneWidget);
    expect(find.byKey(const ValueKey('schulte-board')), findsOneWidget);
    expect(find.text('下一个'), findsOneWidget);
    expect(_textOf(tester, 'schulte-next'), '1');
    expect(_textOf(tester, 'schulte-errors'), '0');
    // 主体不应有纵向滚动容器（一屏放得下）
    final verticalLists = tester
        .widgetList<ListView>(find.byType(ListView))
        .where((w) => w.scrollDirection == Axis.vertical)
        .length;
    expect(verticalLists, 0);
    expect(repo.statsCalls, 1);
  });

  testWidgets('点错会累加错误数，点对推进目标', (tester) async {
    await pumpBrainGame(tester, schultePageForTest());

    // 找一个不是 1 的格子（用格子 key，避免误点统计栏文字）→ 错误 +1
    final wrongCell = find.byWidgetPredicate(
      (w) =>
          w.key is ValueKey<String> &&
          (w.key as ValueKey<String>).value.startsWith('schulte-cell-') &&
          (w.key as ValueKey<String>).value != 'schulte-cell-1',
    );
    await tester.tap(wrongCell.first);
    await tester.pump();

    expect(_textOf(tester, 'schulte-errors'), '1');

    // 点 1 → 目标推进到 2
    await tester.tap(find.byKey(const ValueKey('schulte-cell-1')));
    await tester.pump();
    expect(_textOf(tester, 'schulte-next'), '2');
  });
}
