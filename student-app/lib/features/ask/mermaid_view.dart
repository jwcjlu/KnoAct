import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../../core/theme.dart';

/// 用 WebView 加载 mermaid.js，把 mermaid 源码渲染成 SVG 图。
/// CDN 不可用（无外网）时降级显示源码文本。
class MermaidView extends StatefulWidget {
  const MermaidView({super.key, required this.code, this.height = 320});

  final String code;
  final double height;

  @override
  State<MermaidView> createState() => _MermaidViewState();
}

class _MermaidViewState extends State<MermaidView> {
  WebViewController? _controller;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.transparent)
      ..setNavigationDelegate(NavigationDelegate(onWebResourceError: (_) {
        if (mounted) setState(() => _failed = true);
      }))
      ..loadHtmlString(_html(widget.code));
  }

  @override
  void didUpdateWidget(MermaidView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.code != widget.code) {
      _controller?.loadHtmlString(_html(widget.code));
    }
  }

  String _html(String code) {
    // 转义 mermaid 源码里的反引号/`${}`，避免破坏 JS 模板
    final safe = code.replaceAll('\\', '\\\\').replaceAll('`', '\\`').replaceAll(r'${', r'\${');
    return '''
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>body{margin:0;padding:8px;background:#fff;font-family:sans-serif}svg{max-width:100%;height:auto}</style>
</head>
<body>
<div id="graph"></div>
<script>
const code = `$safe`;
function render() {
  const el = document.getElementById('graph');
  if (typeof mermaid === 'undefined') {
    el.textContent = code;
    return;
  }
  mermaid.initialize({ startOnLoad: false, theme: 'default' });
  mermaid.render('graph-' + Date.now(), code).then(({svg}) => {
    el.innerHTML = svg;
  }).catch(e => {
    el.textContent = code;
  });
}
render();
</script>
</body>
</html>
''';
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) return _Fallback(code: widget.code);
    return SizedBox(
      height: widget.height,
      width: double.infinity,
      child: WebViewWidget(controller: _controller!),
    );
  }
}

class _Fallback extends StatelessWidget {
  const _Fallback({required this.code});

  final String code;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(8)),
        child: SelectableText(code, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
      );
}
