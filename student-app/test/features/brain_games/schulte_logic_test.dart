import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/schulte.dart';

void main() {
  test('三档难度方格尺寸正确', () {
    expect(schulteSizeFor('easy'), 3);
    expect(schulteSizeFor('medium'), 4);
    expect(schulteSizeFor('hard'), 5);
    expect(schulteSizeFor('unknown'), 3);
  });

  test('数字集合完整且被打乱', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      final b = generateSchulte(diff, random: Random(42));
      final n = b.size * b.size;
      expect(b.numbers.length, n);
      expect(b.numbers.toSet(), {for (var i = 1; i <= n; i++) i});
      expect(b.max, n);
    }
  });

  test('同一随机种子可复现，不同种子会不同', () {
    final a = generateSchulte('hard', random: Random(1));
    final b = generateSchulte('hard', random: Random(1));
    final c = generateSchulte('hard', random: Random(2));
    expect(a.numbers, b.numbers);
    expect(a.numbers, isNot(c.numbers));
  });

  test('isComplete：全部点完为真', () {
    final b = generateSchulte('easy', random: Random(9));
    expect(b.isComplete({for (var i = 1; i <= b.max; i++) i}), isTrue);
    expect(b.isComplete({for (var i = 1; i < b.max; i++) i}), isFalse);
  });
}
