import 'dart:ui';

import 'package:pdfrx/pdfrx.dart';

import '../models/reader_selection.dart';
import 'pdf_rect_convert.dart';
import 'selection_geometry.dart';

/// 将 pdfrx 选区转为 [ReaderSelection]（页码 + 归一化 rects）。
Future<ReaderSelection?> mapPdfTextSelection({
  required PdfTextSelection selection,
  required PdfViewerController controller,
}) async {
  if (!selection.hasSelectedText) return null;
  final ranges = await selection.getSelectedTextRanges();
  if (ranges.isEmpty) return null;

  final text = (selection.selectedTextIfLoaded ?? await selection.getSelectedText()).trim();
  if (text.length < 2) return null;

  final pageNumber = ranges.first.pageNumber;
  final doc = controller.document;
  if (pageNumber < 1 || pageNumber > doc.pages.length) {
    return ReaderSelection(quote: text, pageNumber: pageNumber, rectsJson: '');
  }

  final page = doc.pages[pageNumber - 1];
  final pageSize = Size(page.width, page.height);
  final pixelRects = <PageSelectionRect>[];

  for (final range in ranges) {
    if (range.pageNumber != pageNumber) continue;
    for (final frag in range.enumerateFragmentBoundingRects()) {
      pixelRects.add(pdfRectToTopLeft(frag.bounds, page.width, page.height));
    }
  }

  final normalised = normaliseRects(pixelRects, pageSize);
  return ReaderSelection(
    quote: text,
    pageNumber: pageNumber,
    rectsJson: normalised.isEmpty ? '' : encodeRects(normalised),
  );
}
