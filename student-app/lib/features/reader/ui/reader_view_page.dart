import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config.dart';
import '../../../core/theme.dart';
import '../../../core/text_utils.dart';
import '../../../core/widgets.dart';
import '../reader_controller.dart';

class ReaderViewPage extends ConsumerStatefulWidget {
  const ReaderViewPage({super.key});

  @override
  ConsumerState<ReaderViewPage> createState() => _ReaderViewPageState();
}

class _ReaderViewPageState extends ConsumerState<ReaderViewPage> {
  int? _selected;

  Future<void> _onSelectSentence(int i, List<String> sentences) async {
    setState(() => _selected = i);
    final quote = sentences[i];
    await _showActions(quote);
  }

  Future<void> _showActions(String quote) async {
    final ctl = ref.read(readerControllerProvider.notifier);
    final action = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            title: Text('引用：「$quote」', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppColors.gray, fontSize: 13)),
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.translate, color: AppColors.blue),
            title: const Text('查释义'),
            onTap: () => Navigator.pop(ctx, 'glossary'),
          ),
          ListTile(
            leading: const Icon(Icons.edit_note, color: AppColors.green),
            title: const Text('记笔记'),
            onTap: () => Navigator.pop(ctx, 'note'),
          ),
        ]),
      ),
    );
    if (action == null || !mounted) return;

    if (action == 'glossary') {
      final meaning = await ctl.glossary(quote);
      if (mounted && meaning != null) showMessage(context, meaning);
    } else if (action == 'note') {
      await _showNoteInput(quote);
    }
  }

  Future<void> _showNoteInput(String quote) async {
    final controller = TextEditingController();
    final note = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('记笔记'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(hintText: '写下你的笔记…', border: OutlineInputBorder()),
          maxLines: 4,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, controller.text),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (note != null && note.trim().isNotEmpty && mounted) {
      await ref.read(readerControllerProvider.notifier).addNote(quote, note.trim());
      if (mounted) showMessage(context, '笔记已保存');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(readerControllerProvider);
    final lesson = s.currentLesson;
    if (lesson == null) {
      return const Scaffold(body: Center(child: Text('请先选择课文', style: TextStyle(color: AppColors.gray))));
    }
    final sentences = splitSentences(lesson.fullText);
    final baseUrl = resolveApiBase();
    return Scaffold(
      appBar: AppBar(title: Text(lesson.title), backgroundColor: AppColors.bg, scrolledUnderElevation: 0),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        // 教材原页（主视觉：原版课本页面图，对齐 Web 端）
        if (lesson.pages.isNotEmpty) ...[
          for (final page in lesson.pages) ...[
            Image.network(
              '$baseUrl${page.imagePath}',
              fit: BoxFit.contain,
              errorBuilder: (_, _, _) => const SizedBox(height: 200, child: Center(child: Text('页面加载失败', style: TextStyle(color: AppColors.gray)))),
            ),
            const SizedBox(height: 12),
          ],
        ],
        // 课文文本（辅助：划词查释义、记笔记）
        if (sentences.isNotEmpty) ...[
          const SizedBox(height: 4),
          const Text('课文文字', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Text.rich(
            TextSpan(
              children: [
                for (var i = 0; i < sentences.length; i++)
                  WidgetSpan(
                    child: GestureDetector(
                      onTap: () => _onSelectSentence(i, sentences),
                      child: Text(
                        sentences[i],
                        style: TextStyle(height: 1.7, backgroundColor: _selected == i ? AppColors.blueSoft : null),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          const Text('点选句子，可查释义或记笔记', style: TextStyle(color: AppColors.gray, fontSize: 12)),
          const SizedBox(height: 16),
        ],
        // 已有笔记/标注
        if (s.annotations.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('我的笔记', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          for (final a in s.annotations) ...[
            SectionCard(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('「${a.quote}」', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                if (a.note.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(a.note, style: const TextStyle(color: AppColors.gray)),
                ],
              ]),
            ),
            const SizedBox(height: 8),
          ],
        ],
      ]),
    );
  }
}
