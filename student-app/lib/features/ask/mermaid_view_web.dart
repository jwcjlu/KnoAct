import 'dart:convert';

import 'package:flutter/material.dart';

import 'mermaid_fallback.dart';

/// Web / Wasm：用 mermaid.ink 渲染 SVG，避免 WebView 与 dart:html
class MermaidPlatformView extends StatefulWidget {
  const MermaidPlatformView({super.key, required this.code, this.height = 320});

  final String code;
  final double height;

  @override
  State<MermaidPlatformView> createState() => _MermaidInkViewState();
}

class _MermaidInkViewState extends State<MermaidPlatformView> {
  static String _svgUrl(String code) {
    final b64 = base64Encode(utf8.encode(code.trim()))
        .replaceAll('+', '-')
        .replaceAll('/', '_')
        .replaceAll('=', '');
    return 'https://mermaid.ink/svg/$b64';
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: widget.height,
      width: double.infinity,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFE3E6E2)),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.network(
            _svgUrl(widget.code),
            fit: BoxFit.contain,
            loadingBuilder: (context, child, progress) {
              if (progress == null) return child;
              return const Center(child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2)));
            },
            errorBuilder: (context, error, stackTrace) => MermaidFallback(code: widget.code),
          ),
        ),
      ),
    );
  }
}
