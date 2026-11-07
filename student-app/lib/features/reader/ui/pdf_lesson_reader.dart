import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../../../core/theme.dart';
import '../data/pdf_repository.dart' show AnnotationItem;
import '../logic/pdf_asset_url.dart';
import '../logic/pdfrx_selection_mapper.dart';
import '../models/reader_selection.dart';
import 'annotation_page_overlay.dart';

/// 课节 PDF 阅读（pdfrx）：页内划选 + 标注墨迹 overlay。
class PdfLessonReader extends StatefulWidget {
  const PdfLessonReader({
    super.key,
    required this.storagePath,
    required this.startPage,
    required this.endPage,
    required this.annotations,
    required this.onSelection,
    this.onLoadError,
  });

  final String storagePath;
  final int startPage;
  final int endPage;
  final List<AnnotationItem> annotations;
  final ValueChanged<ReaderSelection?> onSelection;
  final ValueChanged<String>? onLoadError;

  @override
  State<PdfLessonReader> createState() => _PdfLessonReaderState();
}

class _PdfLessonReaderState extends State<PdfLessonReader> {
  final _controller = PdfViewerController();
  bool _initialized = false;
  String? _initError;
  Uri? _pdfUri;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  @override
  void didUpdateWidget(covariant PdfLessonReader oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.storagePath != widget.storagePath) {
      setState(() => _pdfUri = Uri.parse(encodedStorageUrl(widget.storagePath)));
    }
  }

  Future<void> _bootstrap() async {
    try {
      await pdfrxFlutterInitialize();
      if (!mounted) return;
      setState(() {
        _initialized = true;
        _pdfUri = Uri.parse(encodedStorageUrl(widget.storagePath));
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _initError = e.toString());
      widget.onLoadError?.call(e.toString());
    }
  }

  Future<void> _onTextSelectionChange(PdfTextSelection selection) async {
    if (!selection.hasSelectedText) {
      widget.onSelection(null);
      return;
    }
    final mapped = await mapPdfTextSelection(selection: selection, controller: _controller);
    widget.onSelection(mapped);
  }

  @override
  Widget build(BuildContext context) {
    if (_initError != null) {
      return Center(child: Text('PDF 初始化失败：$_initError', style: const TextStyle(color: AppColors.gray)));
    }
    if (!_initialized) {
      return const Center(child: CircularProgressIndicator());
    }
    final uri = _pdfUri;
    if (uri == null) {
      return const Center(child: Text('教材 PDF 路径无效'));
    }

    final start = widget.startPage.clamp(1, 99999);
    return PdfViewer.uri(
      uri,
      controller: _controller,
      params: PdfViewerParams(
        calculateInitialPageNumber: (_, _) => start,
        textSelectionParams: PdfTextSelectionParams(
          enabled: true,
          showContextMenuAutomatically: false,
          onTextSelectionChange: _onTextSelectionChange,
        ),
        onPageChanged: (page) {
          final p = page;
          if (p == null) return;
          if (p < widget.startPage || p > widget.endPage) return;
        },
        pageOverlaysBuilder: (context, pageRect, page) {
          if (page.pageNumber < widget.startPage || page.pageNumber > widget.endPage) {
            return [];
          }
          return [
            SizedBox(
              width: pageRect.width,
              height: pageRect.height,
              child: AnnotationPageOverlay(
                page: page,
                pageRect: Rect.fromLTWH(0, 0, pageRect.width, pageRect.height),
                annotations: widget.annotations,
              ),
            ),
          ];
        },
        errorBannerBuilder: (context, error, stackTrace, documentRef) {
          widget.onLoadError?.call(error.toString());
          return Center(child: Text('PDF 加载失败：$error'));
        },
      ),
    );
  }
}
