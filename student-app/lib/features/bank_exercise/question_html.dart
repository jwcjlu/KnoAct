import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// 学库宝 / tiku.cn 等导入题干里的有限 HTML：`br` / `p` / `img` / 常见行内标签。
class QuestionHtmlToken {
  const QuestionHtmlToken(this.kind, this.text);
  final String kind; // text | br | img
  final String text;
}

enum QuestionHtmlBlockKind {
  lead,
  title,
  passage,
  subQuestion,
  option,
  body,
}

final _imgSrcRe = RegExp(r'''\bsrc\s*=\s*(["'])(.*?)\1''', caseSensitive: false);
final _tagRe = RegExp(r'<[^>]+>');
final _dollarRe = RegExp(r'\$([^$]+)\$');
final _entityRe = RegExp(
  r'&(?:nbsp|lt|gt|amp|quot|apos|#x[0-9a-fA-F]+|#\d+);',
);
final _circledParaRe = RegExp(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]');
final _cnOrdinalParaRe = RegExp(r'^(?:[\(（][一二三四五六七八九十百]+[\)）]|[一二三四五六七八九十]+[、．.])');
final _parenSubQRe = RegExp(r'^[\(（](?:\d+|[一二三四五六七八九十]+)[\)）]');
final _dottedNumRe = RegExp(r'^\d+[\.．、]');
final _optionRe = RegExp(r'^[A-Da-d][\.．、\s]');
final _leadRe = RegExp(r'^(?:阅读|朗读|习作|口语交际|写话|看图|阅读下面的文字|阅读短文)[.。．:]?$');
final _promptHintRe = RegExp(r'[？?]|根据|写出|下列|选择|判断|填空|回答|下列说法|请简要|结合原文');

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

      // <p> / </p> 当作段落分隔，便于语文阅读分段
      if (RegExp(r'^</?p(?:\s[^>]*)?>$').hasMatch(lower)) {
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

String questionHtmlBlockPlainText(List<QuestionHtmlToken> block) {
  final buf = StringBuffer();
  for (final t in block) {
    if (t.kind == 'text') buf.write(t.text);
  }
  return buf.toString().trim();
}

/// 按 `br` 切成段落块；连续空行合并，图片单独成块。
List<List<QuestionHtmlToken>> splitQuestionHtmlBlocks(List<QuestionHtmlToken> tokens) {
  final blocks = <List<QuestionHtmlToken>>[];
  var cur = <QuestionHtmlToken>[];

  void push() {
    if (cur.isEmpty) return;
    blocks.add(cur);
    cur = [];
  }

  for (final t in tokens) {
    if (t.kind == 'br') {
      push();
      continue;
    }
    if (t.kind == 'img') {
      push();
      blocks.add([t]);
      continue;
    }
    cur.add(t);
  }
  push();
  return blocks;
}

QuestionHtmlBlockKind classifyQuestionHtmlBlock(
  List<QuestionHtmlToken> block, {
  int index = 0,
  bool materialStarted = false,
  bool questionZone = false,
}) {
  if (block.length == 1 && block.first.kind == 'img') return QuestionHtmlBlockKind.body;
  final text = questionHtmlBlockPlainText(block);
  if (text.isEmpty) return QuestionHtmlBlockKind.body;
  if (_leadRe.hasMatch(text)) return QuestionHtmlBlockKind.lead;
  if (_circledParaRe.hasMatch(text) || _cnOrdinalParaRe.hasMatch(text)) {
    return QuestionHtmlBlockKind.passage;
  }
  if (_optionRe.hasMatch(text)) return QuestionHtmlBlockKind.option;
  if (_parenSubQRe.hasMatch(text)) return QuestionHtmlBlockKind.subQuestion;
  // 「1.」既可能是正文序号也可能是小题：有题干提示语，或已进入材料后的题区，才当小题
  if (_dottedNumRe.hasMatch(text)) {
    if (_promptHintRe.hasMatch(text) || questionZone || materialStarted) {
      return QuestionHtmlBlockKind.subQuestion;
    }
    return QuestionHtmlBlockKind.passage;
  }
  // 篇名只认开头几行，避免把中间短句居中加粗
  final noEndPunct = !RegExp(r'[。？！?!.…]$').hasMatch(text);
  if (!materialStarted &&
      !questionZone &&
      index <= 2 &&
      text.length <= 18 &&
      noEndPunct &&
      !_promptHintRe.hasMatch(text)) {
    return QuestionHtmlBlockKind.title;
  }
  // 材料区里的长段/句末成段 → 阅读正文（无①也会拉开行距）
  if (!questionZone && (text.length >= 28 || RegExp(r'[。！？…]').hasMatch(text))) {
    return QuestionHtmlBlockKind.passage;
  }
  if (questionZone && _promptHintRe.hasMatch(text)) {
    return QuestionHtmlBlockKind.subQuestion;
  }
  return QuestionHtmlBlockKind.body;
}

/// 带上下文的整篇分类：先材料后小题，避免「1.」正文被误判成小题。
List<QuestionHtmlBlockKind> classifyQuestionHtmlBlocks(List<List<QuestionHtmlToken>> blocks) {
  final kinds = <QuestionHtmlBlockKind>[];
  var materialStarted = false;
  var questionZone = false;
  for (var i = 0; i < blocks.length; i++) {
    var kind = classifyQuestionHtmlBlock(
      blocks[i],
      index: i,
      materialStarted: materialStarted,
      questionZone: questionZone,
    );
    // 材料已出现后，第一次明确小题开启题区
    if (materialStarted &&
        !questionZone &&
        (kind == QuestionHtmlBlockKind.subQuestion ||
            (kind == QuestionHtmlBlockKind.body &&
                _promptHintRe.hasMatch(questionHtmlBlockPlainText(blocks[i]))))) {
      kind = QuestionHtmlBlockKind.subQuestion;
      questionZone = true;
    }
    kinds.add(kind);
    if (kind == QuestionHtmlBlockKind.passage || kind == QuestionHtmlBlockKind.title) {
      materialStarted = true;
    }
    if (kind == QuestionHtmlBlockKind.subQuestion || kind == QuestionHtmlBlockKind.option) {
      questionZone = true;
    }
  }
  return kinds;
}

double _gapBefore(QuestionHtmlBlockKind kind, {required bool isFirst}) {
  if (isFirst) return 0;
  switch (kind) {
    case QuestionHtmlBlockKind.lead:
      return 4;
    case QuestionHtmlBlockKind.title:
      return 10;
    case QuestionHtmlBlockKind.passage:
      return 12;
    case QuestionHtmlBlockKind.subQuestion:
      return 16;
    case QuestionHtmlBlockKind.option:
      return 6;
    case QuestionHtmlBlockKind.body:
      return 10;
  }
}

TextStyle _styleFor(QuestionHtmlBlockKind kind, TextStyle base) {
  switch (kind) {
    case QuestionHtmlBlockKind.lead:
      return base.copyWith(
        fontSize: (base.fontSize ?? 15) + 1,
        fontWeight: FontWeight.w700,
        height: 1.55,
        color: const Color(0xFF5C6761),
      );
    case QuestionHtmlBlockKind.title:
      return base.copyWith(
        fontSize: (base.fontSize ?? 15) + 2,
        fontWeight: FontWeight.w700,
        height: 1.45,
        color: const Color(0xFF1A221E),
      );
    case QuestionHtmlBlockKind.passage:
      return base.copyWith(
        fontWeight: FontWeight.w400,
        height: 1.85,
        fontSize: base.fontSize ?? 15,
      );
    case QuestionHtmlBlockKind.subQuestion:
      return base.copyWith(
        fontWeight: FontWeight.w600,
        height: 1.7,
        color: const Color(0xFF1A221E),
      );
    case QuestionHtmlBlockKind.option:
      return base.copyWith(fontWeight: FontWeight.w400, height: 1.65);
    case QuestionHtmlBlockKind.body:
      return base.copyWith(height: 1.75);
  }
}

EdgeInsets _paddingFor(QuestionHtmlBlockKind kind) {
  switch (kind) {
    case QuestionHtmlBlockKind.passage:
      return const EdgeInsets.only(left: 2);
    case QuestionHtmlBlockKind.option:
      return const EdgeInsets.only(left: 14);
    case QuestionHtmlBlockKind.subQuestion:
      return const EdgeInsets.only(left: 2, top: 2);
    case QuestionHtmlBlockKind.title:
      return const EdgeInsets.symmetric(vertical: 2);
    default:
      return EdgeInsets.zero;
  }
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
    final base = style ??
        const TextStyle(
          fontSize: 15,
          height: 1.75,
          color: Color(0xFF202723),
          letterSpacing: 0.15,
        );
    final blocks = splitQuestionHtmlBlocks(tokens);

    // 短选项/单行题干：紧凑 Text.rich
    final plain = questionHtmlBlockPlainText([
      for (final t in tokens)
        if (t.kind != 'br') t,
    ]);
    final isCompact = blocks.length <= 1 && !tokens.any((t) => t.kind == 'img');
    if (isCompact) {
      return Text.rich(
        TextSpan(
          style: base.copyWith(height: base.height ?? 1.75),
          children: [
            if (prefix.isNotEmpty) TextSpan(text: prefix),
            TextSpan(text: plain),
          ],
        ),
      );
    }

    final kinds = classifyQuestionHtmlBlocks(blocks);
    final children = <Widget>[];
    var prefixUsed = prefix.isEmpty;
    var insertedRule = false;
    var sawMaterial = false;

    for (var i = 0; i < blocks.length; i++) {
      final block = blocks[i];
      final kind = kinds[i];

      if (sawMaterial && !insertedRule && kind == QuestionHtmlBlockKind.subQuestion) {
        children.add(const Padding(
          padding: EdgeInsets.only(top: 10, bottom: 6),
          child: Divider(height: 1, thickness: 1, color: Color(0xFFE4E8E5)),
        ));
        insertedRule = true;
      } else {
        final gap = _gapBefore(kind, isFirst: children.isEmpty);
        if (gap > 0) children.add(SizedBox(height: gap));
      }

      if (block.length == 1 && block.first.kind == 'img') {
        children.add(_QuestionNetworkImage(url: block.first.text));
        continue;
      }

      final blockStyle = _styleFor(kind, base);
      final spans = <InlineSpan>[];
      if (!prefixUsed && prefix.isNotEmpty) {
        spans.add(TextSpan(text: prefix, style: blockStyle));
        prefixUsed = true;
      }
      for (final t in block) {
        if (t.kind == 'text') spans.add(TextSpan(text: t.text, style: blockStyle));
      }
      if (spans.isEmpty) continue;

      Widget line = Text.rich(TextSpan(style: blockStyle, children: spans));
      if (kind == QuestionHtmlBlockKind.title) {
        line = SizedBox(width: double.infinity, child: Center(child: line));
      }
      final pad = _paddingFor(kind);
      if (pad != EdgeInsets.zero) {
        line = Padding(padding: pad, child: line);
      }
      children.add(line);

      if (kind == QuestionHtmlBlockKind.passage || kind == QuestionHtmlBlockKind.title) {
        sawMaterial = true;
      }
    }

    if (!prefixUsed && prefix.isNotEmpty) {
      children.insert(0, Text(prefix, style: base));
    }
    if (children.isEmpty) {
      return Text(prefix.isEmpty ? '' : prefix, style: base);
    }
    if (children.length == 1) return children.first;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
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
