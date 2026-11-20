import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

/// 扫雷已开格之间必须有可见分界线，否则一片灰分不出格。
void main() {
  testWidgets('已开格边线颜色明显深于格子底色', (tester) async {
    await pumpBrainGame(tester, minesweeperPageForTest());
    // 首点后会出现已开格
    await tester.tap(find.byKey(const ValueKey('mine-cell-0')).first);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('12×12 困难盘每格仍有可见边界且不溢出', (tester) async {
    await pumpBrainGame(
      tester,
      minesweeperPageForTest(),
      size: const Size(390, 844),
    );
    await tester.tap(find.text('困难'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('mine-cell-0')).first);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
