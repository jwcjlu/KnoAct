import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/sudoku.dart';

void main() {
  test('三档难度规格正确', () {
    expect(sudokuSpecFor('easy').size, 4);
    expect(sudokuSpecFor('easy').boxRows, 2);
    expect(sudokuSpecFor('easy').boxCols, 2);
    expect(sudokuSpecFor('easy').givens, 8);

    expect(sudokuSpecFor('medium').size, 6);
    expect(sudokuSpecFor('medium').boxRows, 2);
    expect(sudokuSpecFor('medium').boxCols, 3);

    expect(sudokuSpecFor('hard').size, 9);
    expect(sudokuSpecFor('hard').boxRows, 3);
    expect(sudokuSpecFor('hard').boxCols, 3);
    expect(sudokuSpecFor('hard').givens, 34);
  });

  test('生成的解是合法数独（行列宫无重复）', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      final p = generateSudoku(diff, random: Random(7));
      final spec = p.spec;
      final n = spec.size;
      for (var r = 0; r < n; r++) {
        expect(p.solution[r].toSet().length, n, reason: '$diff 第 $r 行有重复');
      }
      for (var c = 0; c < n; c++) {
        final col = [for (var r = 0; r < n; r++) p.solution[r][c]];
        expect(col.toSet().length, n, reason: '$diff 第 $c 列有重复');
      }
      for (var br = 0; br < n; br += spec.boxRows) {
        for (var bc = 0; bc < n; bc += spec.boxCols) {
          final box = <int>[];
          for (var i = 0; i < spec.boxRows; i++) {
            for (var j = 0; j < spec.boxCols; j++) {
              box.add(p.solution[br + i][bc + j]);
            }
          }
          expect(box.toSet().length, n, reason: '$diff 宫 ($br,$bc) 有重复');
        }
      }
    }
  });

  test('给定数数量等于难度上限，且给定格与解一致', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      final p = generateSudoku(diff, random: Random(11));
      var count = 0;
      for (var r = 0; r < p.spec.size; r++) {
        for (var c = 0; c < p.spec.size; c++) {
          if (p.givens[r][c] != 0) {
            count++;
            expect(p.givens[r][c], p.solution[r][c]);
          }
        }
      }
      expect(count, p.spec.givens, reason: '$diff 给定数应为 ${p.spec.givens}');
    }
  });

  test('isSolved：全填且等于解才为真', () {
    final p = generateSudoku('easy', random: Random(3));
    expect(p.isSolved(p.solution), isTrue);

    final wrong = [for (final row in p.solution) List<int>.from(row)];
    wrong[0][0] = wrong[0][0] == 1 ? 2 : 1;
    expect(p.isSolved(wrong), isFalse);

    final partial = [for (final row in p.solution) List<int>.from(row)];
    partial[0][0] = 0;
    expect(p.isSolved(partial), isFalse);
  });

  test('isSolved：填满但与解不同（每行仍无重复）也算未通关', () {
    final p = generateSudoku('easy', random: Random(5));
    final alt = [for (final row in p.solution) List<int>.from(row)];
    // 交换第一行前两列，仍合法但不等同于解
    final t = alt[0][0];
    alt[0][0] = alt[0][1];
    alt[0][1] = t;
    expect(p.isSolved(alt), isFalse);
  });
}
