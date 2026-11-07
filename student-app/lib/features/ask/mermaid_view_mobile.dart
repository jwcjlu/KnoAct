import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'mermaid_fallback.dart';
import 'mermaid_html.dart';

class MermaidPlatformView extends StatefulWidget {
  const MermaidPlatformView({super.key, required this.code, this.height = 320});

  final String code;
  final double height;

  @override
  State<MermaidPlatformView> createState() => _MermaidMobileViewState();
}

class _MermaidMobileViewState extends State<MermaidPlatformView> {
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
      ..loadHtmlString(mermaidHtmlDocument(widget.code));
  }

  @override
  void didUpdateWidget(MermaidPlatformView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.code != widget.code) {
      _controller?.loadHtmlString(mermaidHtmlDocument(widget.code));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) return MermaidFallback(code: widget.code);
    return SizedBox(
      height: widget.height,
      width: double.infinity,
      child: WebViewWidget(controller: _controller!),
    );
  }
}
