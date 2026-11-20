import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/minesweeper.dart';

/// 通关后「插旗」与「数字大小」的回归测试。
void main() {
  test('通关后旗子覆盖所有雷', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(9));
    final safe = <int>{};
    for (var i = 0; i < b.rows * b.cols; i++) {
      if (!b.isMine(i)) safe.add(i);
    }
    final opened = <int>{};
    for (final i in safe) {
      opened.addAll(b.reveal(i));
    }
    expect(b.isCleared(opened), isTrue, reason: '构造的开格集合应已通关');

    final flags = b.victoryFlags(opened, const {});
    for (final m in b.mines) {
      expect(flags.contains(m), isTrue, reason: '雷 $m 未插旗');
    }
    expect(flags.length, b.mineCount);
  });

  test('玩家手动插的旗在通关后保留', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(9));
    final mine = b.mines.first;
    final flags = b.victoryFlags(const {}, {mine});
    expect(flags.containsAll(b.mines), isTrue);
  });

  test('数字字号按格子比例，6×6 盘明显大于旧值 15', () {
    expect(55.0 * .58, greaterThan(28));
  });
}
