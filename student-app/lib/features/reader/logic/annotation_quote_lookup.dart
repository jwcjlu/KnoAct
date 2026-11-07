import 'dart:ui';

import 'package:pdfrx/pdfrx.dart';

import 'pdf_rect_convert.dart';
import 'selection_geometry.dart';

/// 无 rects 时按 [quote] 在页内结构化文本中定位，返回归一化矩形（对齐 Web 兜底）。
Future<List<List<double>>> normalisedRectsForQuoteOnPage({
  required PdfPage page,
  required String quote,
}) async {
  final q = quote.trim();
  if (q.isEmpty) return [];

  final structured = await page.loadStructuredText(ensureLoaded: true);
  if (structured.fullText.isEmpty) return [];

  final pixelRects = <PageSelectionRect>[];

  void addFromRange(PdfPageTextRange range) {
    for (final frag in range.enumerateFragmentBoundingRects()) {
      pixelRects.add(pdfRectToTopLeft(frag.bounds, page.width, page.height));
    }
  }

  await for (final range in structured.allMatches(q, caseInsensitive: true)) {
    addFromRange(range);
  }

  if (pixelRects.isEmpty) {
    final lower = structured.fullText.toLowerCase();
    final needle = q.toLowerCase();
    var from = 0;
    while (true) {
      final idx = lower.indexOf(needle, from);
      if (idx < 0) break;
      final end = idx + q.length - 1;
      if (end < structured.fullText.length) {
        addFromRange(structured.getRangeFromAB(idx, end));
      }
      from = idx + 1;
      if (pixelRects.isNotEmpty) break;
    }
  }

  return normaliseRects(pixelRects, Size(page.width, page.height));
}
