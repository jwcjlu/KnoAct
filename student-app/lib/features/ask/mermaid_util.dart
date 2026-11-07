/// 从 answer 文本里提取 mermaid 代码块源码；无则返回 null
String? extractMermaid(String text) {
  final match = RegExp(r'```mermaid\s*\n([\s\S]*?)```', multiLine: true).firstMatch(text);
  if (match != null) return match.group(1)!.trim();
  // 兜底：整段文本就是 mermaid 图（graph/flowchart/sequenceDiagram 等开头）
  if (RegExp(r'^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|mindmap|gantt)\b', multiLine: true).hasMatch(text.trim())) {
    return text.trim();
  }
  return null;
}

/// 去掉 ```mermaid 代码块，只留说明文字（避免与 [MermaidView] 重复撑高）
String stripMermaidFence(String text) {
  final stripped = text.replaceAll(RegExp(r'```mermaid\s*[\s\S]*?```', multiLine: true), '').trim();
  return stripped.isEmpty ? text.trim() : stripped;
}
