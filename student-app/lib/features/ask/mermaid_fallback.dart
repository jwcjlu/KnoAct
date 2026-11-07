import 'package:flutter/material.dart';

import '../../../core/theme.dart';

/// CDN / 渲染失败时展示 mermaid 源码
class MermaidFallback extends StatelessWidget {
  const MermaidFallback({super.key, required this.code});

  final String code;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(8)),
        child: SelectableText(code, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
      );
}
