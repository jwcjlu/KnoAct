/// 按句末标点 + 换行切句（对齐旧版前端 splitSentences 规则）
List<String> splitSentences(String text) {
  if (text.isEmpty) return const [];
  return text
      .split(RegExp(r'(?<=[。！？!?])|\n+'))
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();
}
