import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../../../core/config.dart';

/// Task 0 门禁：验证 pdfrx 网络 PDF 加载与页内划选（验收后可删）。
@visibleForTesting
class PdfReaderSpikePage extends StatefulWidget {
  const PdfReaderSpikePage({super.key});

  @override
  State<PdfReaderSpikePage> createState() => _PdfReaderSpikePageState();
}

/// 本地 `backend/uploads` 与 zhixueban.db `pdf_documents.id=1` 对齐。
const _defaultStoragePath = 'uploads/1_义务教育教科书·语文五年级上册.pdf';

String _encodedAssetUrl(String storagePath) {
  final base = apiBaseForAssets().replaceAll(RegExp(r'/$'), '');
  final normalized = storagePath.startsWith('/') ? storagePath.substring(1) : storagePath;
  final encodedPath = normalized.split('/').map(Uri.encodeComponent).join('/');
  return '$base/$encodedPath';
}

class _PdfReaderSpikePageState extends State<PdfReaderSpikePage> {
  final _urlController = TextEditingController(text: _encodedAssetUrl(_defaultStoragePath));
  final _viewerController = PdfViewerController();
  bool _initialized = false;
  String? _initError;
  Uri? _pdfUri;
  int? _currentPage;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      await pdfrxFlutterInitialize();
      if (!mounted) return;
      setState(() {
        _initialized = true;
        _initError = null;
        _pdfUri = _parseUri(_urlController.text.trim());
      });
    } catch (e, st) {
      debugPrint('[pdfrx spike] initialize failed: $e\n$st');
      if (!mounted) return;
      setState(() {
        _initError = e.toString();
      });
    }
  }

  Uri? _parseUri(String raw) {
    if (raw.isEmpty) return null;
    return Uri.tryParse(raw);
  }

  void _reloadViewer() {
    final uri = _parseUri(_urlController.text.trim());
    setState(() => _pdfUri = uri);
  }

  Future<void> _onTextSelectionChange(PdfTextSelection selection) async {
    if (!selection.hasSelectedText) return;
    final text =
        selection.selectedTextIfLoaded ?? await selection.getSelectedText();
    final ranges = await selection.getSelectedTextRanges();
    final pages = ranges.map((r) => r.pageNumber).toSet().toList()..sort();
    debugPrint(
      '[pdfrx spike] selection pages=$pages len=${text.length} quote=${text.trim()}',
    );
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('pdfrx spike'),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: Text(
              '需后端 8010 提供 PDF（CORS 已开）。可改 URL 后点「加载」。'
              '默认：$_defaultStoragePath',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _urlController,
                    decoration: const InputDecoration(
                      isDense: true,
                      labelText: 'PDF URL',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _reloadViewer(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _reloadViewer,
                  child: const Text('加载'),
                ),
              ],
            ),
          ),
          if (_currentPage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Text('当前页：$_currentPage', style: Theme.of(context).textTheme.labelLarge),
            ),
          Expanded(
            child: switch ((_initError, _initialized, _pdfUri)) {
              (final String err, _, _) => Center(child: Text('pdfrx 初始化失败：$err')),
              (_, false, _) => const Center(child: CircularProgressIndicator()),
              (_, _, null) => const Center(child: Text('请输入有效 PDF URL')),
              (_, _, final Uri uri) => PdfViewer.uri(
                  uri,
                  controller: _viewerController,
                  params: PdfViewerParams(
                    textSelectionParams: PdfTextSelectionParams(
                      enabled: true,
                      showContextMenuAutomatically: false,
                      onTextSelectionChange: _onTextSelectionChange,
                    ),
                    onPageChanged: (page) {
                      if (_currentPage != page) {
                        setState(() => _currentPage = page);
                        debugPrint('[pdfrx spike] page=$page');
                      }
                    },
                  ),
                ),
            },
          ),
        ],
      ),
    );
  }
}
