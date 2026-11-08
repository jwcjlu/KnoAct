import 'package:flutter/material.dart';

class PassageToken {
  const PassageToken(this.kind, this.text);
  final String kind; // text, bold, italic, underline, ipa, blank, h1, h2, br
  final String text;
}

final _inline = RegExp(
  r'(\*\*[^*]+\*\*|\*[^*]+\*|<u>[\s\S]*?</u>|/[^/:\n]{1,40}/|____)',
);

List<PassageToken> tokenizePassage(String src) {
  final out = <PassageToken>[];
  final lines = src.replaceAll('\r\n', '\n').split('\n');
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (i > 0) out.add(const PassageToken('br', '\n'));
    if (line.startsWith('## ')) {
      out.add(PassageToken('h2', line.substring(3)));
      continue;
    }
    if (line.startsWith('# ')) {
      out.add(PassageToken('h1', line.substring(2)));
      continue;
    }
    _tokenizeInline(line, out);
  }
  return out;
}

void _tokenizeInline(String line, List<PassageToken> out) {
  var start = 0;
  for (final m in _inline.allMatches(line)) {
    if (m.start > start) {
      out.add(PassageToken('text', line.substring(start, m.start)));
    }
    final raw = m.group(0)!;
    if (raw == '____') {
      out.add(const PassageToken('blank', ''));
    } else if (raw.startsWith('**') && raw.endsWith('**')) {
      out.add(PassageToken('bold', raw.substring(2, raw.length - 2)));
    } else if (raw.startsWith('*') && raw.endsWith('*')) {
      out.add(PassageToken('italic', raw.substring(1, raw.length - 1)));
    } else if (raw.startsWith('<u>') && raw.endsWith('</u>')) {
      out.add(PassageToken('underline', raw.substring(3, raw.length - 4)));
    } else if (raw.startsWith('/') && raw.endsWith('/')) {
      out.add(PassageToken('ipa', raw.substring(1, raw.length - 1)));
    } else {
      out.add(PassageToken('text', raw));
    }
    start = m.end;
  }
  if (start < line.length) out.add(PassageToken('text', line.substring(start)));
}

class PassageContentView extends StatelessWidget {
  const PassageContentView({super.key, required this.content, this.title});

  final String content;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final tokens = tokenizePassage(content);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (title != null && title!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(title!, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          ),
        Text.rich(_spans(tokens)),
      ],
    );
  }

  static TextSpan _spans(List<PassageToken> tokens) {
    return TextSpan(
      style: const TextStyle(fontSize: 15, height: 1.7, color: Color(0xFF202723)),
      children: [
        for (final t in tokens) _span(t),
      ],
    );
  }

  static InlineSpan _span(PassageToken t) {
    switch (t.kind) {
      case 'br':
        return const TextSpan(text: '\n');
      case 'h1':
      case 'h2':
        return TextSpan(text: '${t.text}\n', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16));
      case 'bold':
        return TextSpan(text: t.text, style: const TextStyle(fontWeight: FontWeight.w700));
      case 'italic':
        return TextSpan(text: t.text, style: const TextStyle(fontStyle: FontStyle.italic));
      case 'underline':
        return TextSpan(text: t.text, style: const TextStyle(decoration: TextDecoration.underline));
      case 'ipa':
        return TextSpan(
          text: '/${t.text}/',
          style: const TextStyle(fontFamily: 'serif', color: Color(0xFF3158E8), fontSize: 13),
        );
      case 'blank':
        return const WidgetSpan(
          alignment: PlaceholderAlignment.baseline,
          baseline: TextBaseline.alphabetic,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 2),
            child: SizedBox(
              width: 48,
              child: DecoratedBox(
                decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFF334038)))),
                child: SizedBox(height: 14),
              ),
            ),
          ),
        );
      default:
        return TextSpan(text: t.text);
    }
  }
}
