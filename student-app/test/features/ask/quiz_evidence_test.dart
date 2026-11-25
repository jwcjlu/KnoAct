import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/ask/ui/quiz_verdict_text.dart';

void main() {
  group('quizVerdictText', () {
    test('confirmed 是正向反馈', () {
      final t = quizVerdictText('confirmed');
      expect(t, contains('关键'));
    });

    test('lucky 指出「答案对但依据不对」，不否定孩子', () {
      final t = quizVerdictText('lucky');
      expect(t, contains('依据'));
      // 不能出现「错」这种否定词
      expect(t.contains('错'), isFalse);
    });

    test('expression_weak 肯定理解，指向表达', () {
      final t = quizVerdictText('expression_weak');
      expect(t, contains('位置'));
      // 关键：不能打红叉式的否定
      expect(t.contains('错'), isFalse);
    });

    test('not_understood 引导回去看', () {
      final t = quizVerdictText('not_understood');
      expect(t, contains('再看'));
    });

    test('unknown 不显示任何出处评价', () {
      expect(quizVerdictText('unknown'), isEmpty);
    });
  });

  group('quizVerdictColor', () {
    test('expression_weak 不用错误色', () {
      expect(
        quizVerdictColor('expression_weak'),
        isNot(const Color(0xFFC05B4A)),
      );
    });

    test('confirmed 用绿色', () {
      expect(quizVerdictColor('confirmed'), const Color(0xFF2E8B5A));
    });

    test('lucky 与 not_understood 用琥珀色', () {
      expect(quizVerdictColor('lucky'), const Color(0xFFDC872D));
      expect(quizVerdictColor('not_understood'), const Color(0xFFDC872D));
    });

    test('expression_weak 用中性灰，不用红也不绿', () {
      expect(quizVerdictColor('expression_weak'), const Color(0xFF78817B));
    });
  });
}
