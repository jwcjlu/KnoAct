import 'package:flutter/material.dart';

// Web 为默认实现；仅在有 dart:io 的原生平台用 WebView（Wasm Web 无 dart.library.html，不能靠 html 判断）
import 'mermaid_view_web.dart' if (dart.library.io) 'mermaid_view_mobile.dart' as platform;

/// 渲染 mermaid：Web/Wasm 用 mermaid.ink 图片；Android 用 WebView。
class MermaidView extends StatelessWidget {
  const MermaidView({super.key, required this.code, this.height = 320});

  final String code;
  final double height;

  @override
  Widget build(BuildContext context) => platform.MermaidPlatformView(code: code, height: height);
}
