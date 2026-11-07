import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/config.dart';
import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../ask/ask_controller.dart';
import '../../ask/ui/ask_panel.dart';
import '../../assignment/assignment_controller.dart';
import '../../assignment/ui/assignment_sidebar.dart';
import '../models/reader_selection.dart';
import '../reader_controller.dart';
import '../data/pdf_repository.dart';
import 'pdf_lesson_reader.dart';
import 'reader_selection_bar.dart';

/// 沉浸阅读（教材页图 + 划句引用 + 本课作业 + 对话伴学），对齐 Web 个性化学习全屏页
class ReaderViewPage extends ConsumerStatefulWidget {
  const ReaderViewPage({super.key, this.initialLessonId});

  /// 深链 `?lesson=`；未传时用本地记录的上次课文
  final int? initialLessonId;

  @override
  ConsumerState<ReaderViewPage> createState() => _ReaderViewPageState();
}

const _kChatWidthKey = 'knoact_reader_chat_width';
const _kChatHeightKey = 'knoact_reader_chat_height';

class _ReaderViewPageState extends ConsumerState<ReaderViewPage> {
  bool _chatOpen = true;
  bool _booting = true;
  String? _bootError;
  double _chatWidth = 380;
  double _chatHeightFactor = 0.42;
  ReaderSelection? _selection;
  String _annotColor = 'yellow';

  @override
  void initState() {
    super.initState();
    _loadPanelSizes();
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _loadPanelSizes() async {
    final p = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _chatWidth = p.getDouble(_kChatWidthKey) ?? 380;
      _chatHeightFactor = p.getDouble(_kChatHeightKey) ?? 0.42;
    });
  }

  Future<void> _saveChatWidth() async {
    final p = await SharedPreferences.getInstance();
    await p.setDouble(_kChatWidthKey, _chatWidth);
  }

  Future<void> _saveChatHeight() async {
    final p = await SharedPreferences.getInstance();
    await p.setDouble(_kChatHeightKey, _chatHeightFactor);
  }

  Future<void> _bootstrap() async {
    final ctl = ref.read(readerControllerProvider.notifier);
    if (ref.read(readerControllerProvider).currentLesson == null) {
      try {
        final ok = await ctl.prepareView(lessonIdHint: widget.initialLessonId);
        if (!ok && mounted) _bootError = '没有可用的教材或课文';
      } catch (_) {
        if (mounted) _bootError = '加载失败，请检查网络或后端 8010';
      }
    }
    if (mounted) setState(() => _booting = false);
  }

  Widget _pageImage(String imageUrl) {
    const err = SizedBox(
      height: 240,
      child: Center(child: Text('页面加载失败', style: TextStyle(color: AppColors.gray))),
    );
    const loading = SizedBox(
      height: 240,
      child: Center(child: CircularProgressIndicator()),
    );
    if (kIsWeb) {
      return Image.network(
        imageUrl,
        fit: BoxFit.contain,
        loadingBuilder: (ctx, child, progress) => progress == null ? child : loading,
        errorBuilder: (context, error, stackTrace) => err,
      );
    }
    return CachedNetworkImage(
      imageUrl: imageUrl,
      fit: BoxFit.contain,
      placeholder: (_, _) => loading,
      errorWidget: (_, _, _) => err,
    );
  }

  void _onPdfSelection(ReaderSelection? sel) {
    setState(() => _selection = sel);
    if (sel != null && sel.isValid) {
      ref.read(askControllerProvider.notifier).setSelected(sel.quote);
      setState(() => _chatOpen = true);
    }
  }

  ReaderSelection? get _activeSelection => _selection?.isValid == true ? _selection : null;

  Future<void> _applyHighlight(String kind) async {
    final sel = _activeSelection;
    if (sel == null) return;
    await ref.read(readerControllerProvider.notifier).addHighlight(
          sel.quote,
          kind: kind,
          color: _annotColor,
          pageNumber: sel.pageNumber,
          rects: sel.rectsJson,
        );
    if (mounted) {
      showMessage(context, kind == 'underline' ? '已添加下划线' : '已添加划线');
      setState(() => _selection = null);
    }
  }

  Future<void> _saveNote(String note) async {
    final sel = _activeSelection;
    if (sel == null || note.isEmpty) return;
    await ref.read(readerControllerProvider.notifier).addNote(
          sel.quote,
          note,
          color: _annotColor,
          pageNumber: sel.pageNumber,
          rects: sel.rectsJson,
        );
    if (mounted) {
      showMessage(context, '笔记已保存');
      setState(() => _selection = null);
    }
  }

  Future<void> _glossaryFromSelection() async {
    final sel = _activeSelection;
    if (sel == null) return;
    final meaning = await ref.read(readerControllerProvider.notifier).glossary(
          sel.quote,
          pageNumber: sel.pageNumber,
          rects: sel.rectsJson,
        );
    if (mounted && meaning != null && meaning.isNotEmpty) {
      showMessage(context, meaning);
      setState(() => _selection = null);
    }
  }

  Future<void> _askChip(String prompt) async {
    final sel = _activeSelection;
    if (sel == null) return;
    final ask = ref.read(askControllerProvider.notifier);
    ask.setSelected(sel.quote);
    await ask.send(prompt);
    if (mounted) setState(() => _selection = null);
  }

  Widget _colResizeHandle({required ValueChanged<double> onDrag, required VoidCallback onEnd}) {
    return MouseRegion(
      cursor: SystemMouseCursors.resizeColumn,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onHorizontalDragUpdate: (d) => onDrag(d.delta.dx),
        onHorizontalDragEnd: (_) => onEnd(),
        child: Container(
          width: 6,
          color: AppColors.line,
          child: const Center(child: Icon(Icons.more_vert, size: 14, color: AppColors.gray)),
        ),
      ),
    );
  }

  Widget _rowResizeHandle({required ValueChanged<double> onDrag, required VoidCallback onEnd}) {
    return MouseRegion(
      cursor: SystemMouseCursors.resizeRow,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onVerticalDragUpdate: (d) => onDrag(d.delta.dy),
        onVerticalDragEnd: (_) => onEnd(),
        child: Container(
          height: 6,
          color: AppColors.line,
        ),
      ),
    );
  }

  Widget _readerBody(PdfLesson lesson, List<AnnotationItem> annotations, String? storagePath, bool chatBlocked) {
    final sel = _activeSelection;
    Widget reader;
    if (storagePath != null && storagePath.isNotEmpty) {
      reader = PdfLessonReader(
        storagePath: storagePath,
        startPage: lesson.startPage,
        endPage: lesson.endPage,
        annotations: annotations,
        onSelection: _onPdfSelection,
      );
    } else {
      reader = _pngFallbackReader(lesson);
    }

    return ColoredBox(
      color: const Color(0xFFEEECE8),
      child: Stack(
        children: [
          Positioned.fill(child: reader),
          if (sel != null)
            Positioned(
              left: 12,
              right: 12,
              top: 12,
              child: ReaderSelectionBar(
                selection: sel,
                chatDisabled: chatBlocked,
                annotColor: _annotColor,
                onPickColor: (c) => setState(() => _annotColor = c),
                onHighlight: () => _applyHighlight('highlight'),
                onUnderline: () => _applyHighlight('underline'),
                onSaveNote: _saveNote,
                onGlossary: _glossaryFromSelection,
                onAsk: () => _askChip('请结合课文解释下面这段：「${sel.quote}」'),
                onExplain: () => _askChip('用小学生能懂的话解释：「${sel.quote}」'),
                onTranslate: () => _askChip('请翻译并讲解：「${sel.quote}」'),
                onClose: () => setState(() => _selection = null),
              ),
            ),
        ],
      ),
    );
  }

  Widget _pngFallbackReader(PdfLesson lesson) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 12),
          child: Text(
            '这本教材暂时没有 PDF 文件，无法页内划选。请联系家长检查上传或换一本教材。',
            style: TextStyle(color: AppColors.gray, fontSize: 13, height: 1.45),
          ),
        ),
        if (lesson.pages.isNotEmpty)
          for (final page in lesson.pages) ...[
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 920),
                child: Material(
                  elevation: 1,
                  color: Colors.white,
                  child: _pageImage('${resolveApiAssetUrl(page.imagePath)}?v=${lesson.documentVersion}'),
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],
      ]),
    );
  }

  Widget _sidePanel(PdfLesson lesson, bool chatBlocked, List<AnnotationItem> annotations) {
    return Container(
      color: AppColors.bg,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
        children: [
          if (annotations.isNotEmpty) ...[
            const Text('我的标注', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            const SizedBox(height: 6),
            for (final a in annotations.take(12)) ...[
              SectionCard(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      a.kind == 'glossary'
                          ? '生词'
                          : (a.kind == 'note' ? '笔记' : (a.kind == 'underline' ? '下划线' : '划线')),
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.blue),
                    ),
                    const SizedBox(height: 4),
                    Text('「${a.quote}」', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
                    if (a.note.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(a.note, style: const TextStyle(fontSize: 12, color: AppColors.gray)),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 8),
            ],
            const SizedBox(height: 8),
          ],
          const Text('对话伴学', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          const SizedBox(height: 2),
          const Text('回答会指明原文出处', style: TextStyle(fontSize: 12, color: AppColors.gray)),
          const SizedBox(height: 12),
          AssignmentSidebar(lessonTitle: lesson.title),
          const SizedBox(height: 12),
          if (!chatBlocked && ref.watch(askControllerProvider).messages.isEmpty && !ref.watch(askControllerProvider).busy) ...[
            const Text('边读边问，随时解惑', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            const Text(
              '选中正文里任意一段，就能追问、解释或翻译它。',
              style: TextStyle(fontSize: 12, color: AppColors.gray, height: 1.45),
            ),
            const SizedBox(height: 12),
          ],
          AskPanel(chatDisabled: chatBlocked),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(readerControllerProvider);
    final lesson = s.currentLesson;
    if (_booting && lesson == null) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text('正在加载课文…', style: TextStyle(color: AppColors.gray)),
            ],
          ),
        ),
      );
    }
    if (lesson == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('阅读')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_bootError ?? '请先选择课文', style: const TextStyle(color: AppColors.gray)),
              const SizedBox(height: 16),
              FilledButton(onPressed: () => context.go('/reader'), child: const Text('去选择教材')),
            ],
          ),
        ),
      );
    }

    final assignment = ref.watch(assignmentControllerProvider);
    final chatBlocked = assignmentBlocksChat(assignment);
    final pageHint = lesson.pages.isNotEmpty
        ? '${lesson.startPage}–${lesson.endPage} 页'
        : '第 ${lesson.startPage}–${lesson.endPage} 页';

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Material(
              color: Colors.white,
              elevation: 0,
              child: Container(
                decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.line))),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                child: Row(children: [
                  IconButton(
                    tooltip: '返回',
                    onPressed: () => context.go('/reader'),
                    icon: const Icon(Icons.arrow_back),
                  ),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(lesson.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
                      Text(pageHint, style: const TextStyle(fontSize: 12, color: AppColors.gray)),
                    ]),
                  ),
                  IconButton(
                    tooltip: '本课作业',
                    onPressed: () => setState(() => _chatOpen = true),
                    icon: const Icon(Icons.edit_note_outlined),
                  ),
                  IconButton(
                    tooltip: _chatOpen ? '收起对话' : '展开对话',
                    onPressed: () => setState(() => _chatOpen = !_chatOpen),
                    icon: Icon(_chatOpen ? Icons.chat_bubble : Icons.chat_bubble_outline),
                  ),
                ]),
              ),
            ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, c) {
                  final wide = c.maxWidth >= 680;
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(child: _readerBody(lesson, s.annotations, s.storagePath, chatBlocked)),
                        if (_chatOpen) ...[
                          _colResizeHandle(
                            onDrag: (dx) => setState(() => _chatWidth = (_chatWidth - dx).clamp(280.0, 560.0)),
                            onEnd: _saveChatWidth,
                          ),
                          SizedBox(
                            width: _chatWidth.clamp(280.0, c.maxWidth * 0.55),
                            child: ColoredBox(
                              color: AppColors.bg,
                              child: _sidePanel(lesson, chatBlocked, s.annotations),
                            ),
                          ),
                        ],
                      ],
                    );
                  }
                  final h = (c.maxHeight * _chatHeightFactor).clamp(220.0, c.maxHeight * 0.65);
                  return Column(
                    children: [
                      Expanded(child: _readerBody(lesson, s.annotations, s.storagePath, chatBlocked)),
                      if (_chatOpen) ...[
                        _rowResizeHandle(
                          onDrag: (dy) {
                            final next = _chatHeightFactor - dy / c.maxHeight;
                            setState(() => _chatHeightFactor = next.clamp(0.28, 0.65));
                          },
                          onEnd: _saveChatHeight,
                        ),
                        SizedBox(height: h, child: ColoredBox(color: AppColors.bg, child: _sidePanel(lesson, chatBlocked, s.annotations))),
                      ],
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
