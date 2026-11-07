import 'package:flutter/material.dart';

/// 页内划选结果（对齐 Web selectedQuote / selectedPage / selectedRects）。
class ReaderSelection {
  const ReaderSelection({
    required this.quote,
    required this.pageNumber,
    required this.rectsJson,
    this.anchor,
  });

  final String quote;
  final int pageNumber;
  final String rectsJson;
  final Rect? anchor;

  bool get isValid => quote.trim().length >= 2;
}
