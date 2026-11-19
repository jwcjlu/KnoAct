import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/minesweeper.dart';

void main() {
  test('三档难度规格正确', () {
    expect(minesweeperSpecFor('easy'), (rows: 6, cols: 6, mines: 5));
    expect(minesweeperSpecFor('medium'), (rows: 9, cols: 9, mines: 12));
    expect(minesweeperSpecFor('hard'), (rows: 12, cols: 12, mines: 24));
  });

  test('首点安全：指定格永不是雷', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      for (var seed = 0; seed < 20; seed++) {
        final b = generateMinesweeper(diff, safeIndex: 0, random: Random(seed));
        expect(b.isMine(0), isFalse, reason: '$diff seed=$seed 首点是雷');
      }
    }
  });

  test('雷数正确且相邻计数正确', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(7));
    expect(b.mines.length, 5);
    final rows = b.rows, cols = b.cols;
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        if (b.isMineAt(r, c)) continue;
        var n = 0;
        for (var dr = -1; dr <= 1; dr++) {
          for (var dc = -1; dc <= 1; dc++) {
            if (dr == 0 && dc == 0) continue;
            if (b.isMineAt(r + dr, c + dc)) n++;
          }
        }
        expect(b.adjacentAt(r, c), n, reason: '($r,$c) 相邻雷数不对');
      }
    }
  });

  test('越界访问返回 false / -1 而不抛异常', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(3));
    expect(b.isMineAt(-1, 0), isFalse);
    expect(b.isMineAt(99, 99), isFalse);
    expect(b.adjacentAt(-1, 0), -1);
  });

  test('reveal 空白格扩散，遇数字停止', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(11));
    final opened = b.reveal(0);
    expect(opened, isNotEmpty);
    expect(opened.contains(0), isTrue);
    // 扩散出来的格子都不能是雷
    for (final i in opened) {
      expect(b.isMine(i), isFalse);
    }
  });

  test('isCleared：所有非雷格开完才算通关', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(5));
    final allSafe = {
      for (var i = 0; i < b.rows * b.cols; i++)
        if (!b.isMine(i)) i,
    };
    expect(b.isCleared(allSafe), isTrue);
    expect(b.isCleared(allSafe.difference({0})), isFalse);
  });
}
