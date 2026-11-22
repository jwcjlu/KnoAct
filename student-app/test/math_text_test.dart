// student-app/test/math_text_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/widgets/math_text.dart';

void main() {
  List<InlineSpan> spansOf(String text) => buildMathSpans(text);

  test('短公式降级为纯文本（不走 Math.tex）', () {
    final spans = spansOf(r'一个数 $2.5$ 倍');
    final widgets = spans.whereType<WidgetSpan>().toList();
    expect(widgets, isEmpty, reason: '2.5 只有 3 字符，应降级');
    final text = spans.whereType<TextSpan>().map((s) => s.text ?? '').join();
    expect(text, contains('2.5'));
    expect(text, isNot(contains(r'$')));
  });

  test('长公式用 WidgetSpan', () {
    final spans = spansOf(r'计算 $\frac{3}{4}$ 的值');
    expect(spans.whereType<WidgetSpan>().length, 1);
  });

  test('不含 \$ 时只产生一个 TextSpan', () {
    final spans = spansOf('求涂色部分的面积');
    expect(spans.whereType<WidgetSpan>(), isEmpty);
    expect(spans.whereType<TextSpan>().length, 1);
  });

  test('\$ 不配对时按普通文本处理，不吞字符', () {
    final spans = spansOf(r'只有 $一个 美元符号');
    expect(spans.whereType<WidgetSpan>(), isEmpty);
    final text = spans.whereType<TextSpan>().map((s) => s.text ?? '').join();
    expect(text, contains(r'$'));
  });

  test('多个长公式产生多个 WidgetSpan', () {
    // 注意：短公式（≤6 字符且无 \ ^ _ { }）会降级成纯文本，
    // 所以这里必须用长公式，否则测不到 WidgetSpan
    final spans = spansOf(r'$\frac{1}{2}+\frac{3}{4}$ 和 $\frac{5}{6}$');
    expect(spans.whereType<WidgetSpan>().length, 2);
  });

  test('空串返回空列表', () {
    expect(spansOf(''), isEmpty);
  });

  test('上标含 ^ 不降级', () {
    final spans = spansOf(r'$x^2$');
    expect(spans.whereType<WidgetSpan>().length, 1);
  });
}
