import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// 学库宝 / tiku.cn 等导入题干里的有限 HTML：`br` / `img` / 常见行内标签。
class QuestionHtmlToken {
  const QuestionHtmlToken(this.kind, this.text);
  final String kind; // text | br | img
  final String text;
}

final _imgSrcRe = RegExp(r'''\bsrc\s*=\s*(["'])(.*?)\1''', caseSensitive: false);
final _tagRe = RegExp(r'<[^>]+>');
final _dollarRe = RegExp(r'\$([^$]+)\$');
final _entityRe = RegExp(
  r'&(?:nbsp|lt|gt|amp|quot|apos|#x[0-9a-fA-F]+|#\d+);',
);

bool _isSafeHttpUrl(String url) {
  final u = url.trim();
  return u.startsWith('https://') || u.startsWith('http://');
}

String decodeHtmlEntities(String s) {
  return s.replaceAllMapped(_entityRe, (m) {
    final raw = m.group(0)!;
    switch (raw) {
      case '&nbsp;':
        return ' ';
      case '&lt;':
        return '<';
      case '&gt;':
        return '>';
      case '&amp;':
        return '&';
      case '&quot;':
        return '"';
      case '&apos;':
        return "'";
    }
    if (raw.startsWith('&#x') || raw.startsWith('&#X')) {
      final hex = raw.substring(3, raw.length - 1);
      final code = int.tryParse(hex, radix: 16);
      if (code != null) return String.fromCharCode(code);
    } else if (raw.startsWith('&#')) {
      final dec = raw.substring(2, raw.length - 1);
      final code = int.tryParse(dec);
      if (code != null) return String.fromCharCode(code);
    }
    return raw;
  });
}

String _stripDollars(String s) => s.replaceAllMapped(_dollarRe, (m) => m.group(1)!);

void _emitText(List<QuestionHtmlToken> out, String buf) {
  final text = _stripDollars(decodeHtmlEntities(buf));
  if (text.isEmpty) return;
  out.add(QuestionHtmlToken('text', text));
}

/// 将题干/选项 HTML 拆成可渲染 token；脚本与非 http(s) 图片丢弃。
List<QuestionHtmlToken> tokenizeQuestionHtml(String src) {
  final out = <QuestionHtmlToken>[];
  final s = src;
  var i = 0;
  final buf = StringBuffer();

  void flush() {
    if (buf.isEmpty) return;
    _emitText(out, buf.toString());
    buf.clear();
  }

  while (i < s.length) {
    if (s.startsWith('<', i)) {
      final close = s.indexOf('>', i);
      if (close < 0) {
        buf.write(s.substring(i));
        break;
      }
      final tag = s.substring(i, close + 1);
      final lower = tag.toLowerCase();

      if (RegExp(r'^<br\s*/?>$').hasMatch(lower)) {
        flush();
        out.add(const QuestionHtmlToken('br', '\n'));
        i = close + 1;
        continue;
      }

      if (lower.startsWith('<img')) {
        flush();
        final m = _imgSrcRe.firstMatch(tag);
        final url = (m?.group(2) ?? '').trim();
        if (_isSafeHttpUrl(url)) {
          out.add(QuestionHtmlToken('img', url));
        }
        i = close + 1;
        continue;
      }

      if (RegExp(r'^</?(?:script|style)[\s>]').hasMatch(lower)) {
        flush();
        final name = lower.startsWith('</')
            ? lower.substring(2).split(RegExp(r'[\s>]')).first
            : lower.substring(1).split(RegExp(r'[\s>]')).first;
        final endTag = '</$name>';
        final endAt = s.toLowerCase().indexOf(endTag, close + 1);
        i = endAt < 0 ? s.length : endAt + endTag.length;
        continue;
      }

      // 其它标签仅剥壳，保留内部文本
      if (_tagRe.hasMatch(tag)) {
        i = close + 1;
        continue;
      }
    }

    buf.write(s[i]);
    i++;
  }
  flush();
  return out;
}

class QuestionHtmlView extends StatelessWidget {
  const QuestionHtmlView({
    super.key,
    required this.html,
    this.prefix = '',
    this.style,
  });

  final String html;
  final String prefix;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final tokens = tokenizeQuestionHtml(html);
    final base = style ?? const TextStyle(fontSize: 15, height: 1.5, color: Color(0xFF202723));
    // 图片用独立 Image（Web 上走 HTML <img> 绕开 CORS），不放进 Text.rich WidgetSpan
    final children = <Widget>[];
    var spans = <InlineSpan>[];

    void flushText() {
      if (spans.isEmpty) return;
      children.add(Text.rich(TextSpan(style: base, children: List.of(spans))));
      spans = [];
    }

    if (prefix.isNotEmpty) {
      spans.add(TextSpan(text: prefix, style: base));
    }
    for (final t in tokens) {
      switch (t.kind) {
        case 'br':
          spans.add(const TextSpan(text: '\n'));
        case 'img':
          flushText();
          children.add(_QuestionNetworkImage(url: t.text));
        default:
          spans.add(TextSpan(text: t.text, style: base));
      }
    }
    flushText();

    if (children.length == 1) return children.first;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) const SizedBox(height: 6),
          children[i],
        ],
      ],
    );
  }
}

class _QuestionNetworkImage extends StatelessWidget {
  const _QuestionNetworkImage({required this.url});
  final String url;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420, maxHeight: 280),
      child: Image.network(
        url,
        fit: BoxFit.contain,
        // 学库宝 CDN 无 CORS；Web 用 HTML <img> 才能显示
        webHtmlElementStrategy: kIsWeb ? WebHtmlElementStrategy.prefer : WebHtmlElementStrategy.never,
        loadingBuilder: (context, child, progress) {
          if (progress == null) return child;
          return const SizedBox(
            width: 48,
            height: 48,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          );
        },
        errorBuilder: (_, _, _) => const Icon(Icons.broken_image_outlined, size: 36),
      ),
    );
  }
}
