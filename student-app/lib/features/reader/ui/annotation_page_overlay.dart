import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../data/pdf_repository.dart' show AnnotationItem;
import '../logic/annotation_quote_lookup.dart';
import '../logic/selection_geometry.dart';

const _inkSwatch = <String, Color>{
  'yellow': Color(0xAAFACD5A),
  'green': Color(0xAA8CDB94),
  'blue': Color(0xAA7AC0FA),
  'pink': Color(0xAAFAA1C7),
  'purple': Color(0xAAC7AEFA),
};

/// 单页标注墨迹（含 quote 回退定位）。
class AnnotationPageOverlay extends StatefulWidget {
  const AnnotationPageOverlay({
    super.key,
    required this.page,
    required this.pageRect,
    required this.annotations,
  });

  final PdfPage page;
  final Rect pageRect;
  final List<AnnotationItem> annotations;

  @override
  State<AnnotationPageOverlay> createState() => _AnnotationPageOverlayState();
}

class _AnnotationPageOverlayState extends State<AnnotationPageOverlay> {
  List<Widget> _marks = const [];
  Object? _cacheKey;

  @override
  void initState() {
    super.initState();
    _rebuild();
  }

  @override
  void didUpdateWidget(covariant AnnotationPageOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    final key = Object.hash(
      widget.page.pageNumber,
      widget.annotations.length,
      widget.annotations.fold<int>(0, (p, a) => p ^ a.id),
    );
    if (key != _cacheKey) _rebuild();
  }

  Future<void> _rebuild() async {
    final pageNo = widget.page.pageNumber;
    final pageRect = widget.pageRect;
    final marks = <Widget>[];

    for (final a in widget.annotations) {
      if (a.pageNumber != pageNo) continue;

      var rects = decodeRects(a.rects);
      if (rects.isEmpty && a.quote.trim().isNotEmpty) {
        try {
          rects = await normalisedRectsForQuoteOnPage(page: widget.page, quote: a.quote);
        } catch (_) {
          rects = const [];
        }
      }
      if (rects.isEmpty) continue;

      final color = a.kind == 'glossary'
          ? const Color(0xAA8CDB94)
          : (_inkSwatch[a.color] ?? _inkSwatch['yellow']!);
      final isUnderline = a.kind == 'underline';

      for (final r in rects) {
        if (r.length < 4) continue;
        final left = pageRect.width * r[0];
        final top = pageRect.height * r[1];
        final w = pageRect.width * (r[2] - r[0]);
        final h = pageRect.height * (r[3] - r[1]);
        marks.add(
          Positioned(
            left: left,
            top: top,
            width: w.clamp(1, pageRect.width),
            height: isUnderline ? 3 : h.clamp(2, pageRect.height),
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: isUnderline ? Colors.transparent : color,
                  border: isUnderline ? Border(bottom: BorderSide(color: color.withValues(alpha: 1), width: 2)) : null,
                ),
              ),
            ),
          ),
        );
      }
    }

    if (!mounted) return;
    setState(() {
      _marks = marks;
      _cacheKey = Object.hash(
        widget.page.pageNumber,
        widget.annotations.length,
        widget.annotations.fold<int>(0, (p, a) => p ^ a.id),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Stack(children: _marks);
  }
}
