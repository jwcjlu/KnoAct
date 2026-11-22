// student-app/lib/core/widgets/math_text.dart
import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

/// 把「中文 + `$...$` 数学式」混合文本切成 InlineSpan 列表。
///
/// 规则（实测得出，见规格 §10.1）：
/// 1. 只匹配**成对**的 `$...$`；不配对时全文按普通文本处理，绝不吞字符。
/// 2. **短公式降级**：LaTeX 源码 ≤ 6 字符且不含 `\ ^ _ { }`（如 `2.5`、`15`、`x`）
///    去掉 `$` 用普通 TextSpan 渲染，避免 WidgetSpan 整块换行把后面的
///    「（　）」拆到下一行。
/// 3. 长公式用 WidgetSpan 行内渲染，`onErrorFallback` 保证坏公式不崩。
List<InlineSpan> buildMathSpans(String text, {TextStyle? style}) {
  final src = text;
  if (src.isEmpty) return const [];
  final base = style;

  bool shouldDowngrade(String tex) {
    if (tex.length > 6) return false;
    for (final ch in [r'\', '^', '_', '{', '}']) {
      if (tex.contains(ch)) return false;
    }
    return true;
  }

  final spans = <InlineSpan>[];
  final re = RegExp(r'\$([^$]+)\$');
  var last = 0;
  for (final m in re.allMatches(src)) {
    if (m.start > last) {
      spans.add(TextSpan(text: src.substring(last, m.start), style: base));
    }
    final tex = m.group(1) ?? '';
    if (shouldDowngrade(tex)) {
      spans.add(TextSpan(text: tex, style: base));
    } else {
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        child: Math.tex(
          tex,
          textStyle: base,
          onErrorFallback: (e) => Text(
            tex,
            style: (base ?? const TextStyle()).copyWith(color: Colors.red),
          ),
        ),
      ));
    }
    last = m.end;
  }
  if (last < src.length) {
    spans.add(TextSpan(text: src.substring(last), style: base));
  }
  return spans;
}

/// 渲染一段可能含 `$...$` 的文本。中文与公式混排、自动换行。
class MathText extends StatelessWidget {
  const MathText(this.text, {super.key, this.style, this.maxLines});

  final String text;
  final TextStyle? style;
  final int? maxLines;

  @override
  Widget build(BuildContext context) {
    final spans = buildMathSpans(text, style: style);
    if (spans.isEmpty) return const SizedBox.shrink();
    return Text.rich(
      TextSpan(style: style, children: spans),
      maxLines: maxLines,
      overflow: maxLines == null ? TextOverflow.clip : TextOverflow.ellipsis,
    );
  }
}
