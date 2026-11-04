import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../reader_controller.dart';
import '../data/pdf_repository.dart';

/// 个性化学习入口：教材列表 → 选课 → 进入阅读
class ReaderHomePage extends ConsumerWidget {
  const ReaderHomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(readerControllerProvider);
    final ctl = ref.read(readerControllerProvider.notifier);
    return Scaffold(
      appBar: AppBar(title: const Text('个性化学习'), backgroundColor: AppColors.bg, scrolledUnderElevation: 0),
      body: s.lessons.isNotEmpty
          ? _LessonList(
              lessons: s.lessons,
              onOpen: (l) async {
                await ctl.openLesson(l);
                if (context.mounted) context.go('/reader/view');
              },
            )
          : s.documents.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => ErrorCard(message: '教材加载失败，请检查网络或后端服务', onRetry: ctl.loadDocuments),
              data: (docs) => docs.isEmpty
                  ? const Center(child: Text('暂无教材，请在家长端上传 PDF', style: TextStyle(color: AppColors.gray)))
                  : _DocumentList(docs: docs, onSelect: ctl.loadLessons),
            ),
    );
  }
}

class _DocumentList extends StatelessWidget {
  const _DocumentList({required this.docs, required this.onSelect});

  final List<PdfDoc> docs;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(20), children: [
        const Text('我的教材', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        const Text('选择教材进入阅读，在正文里划词、记笔记、查释义', style: TextStyle(color: AppColors.gray)),
        const SizedBox(height: 16),
        for (final d in docs) ...[
          SectionCard(
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 8),
              leading: const Icon(Icons.menu_book, color: AppColors.blue),
              title: Text(d.filename),
              subtitle: Text('${d.subject} · ${d.lessonCount} 课'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => onSelect(d.id),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ]);
}

class _LessonList extends StatelessWidget {
  const _LessonList({required this.lessons, required this.onOpen});

  final List<PdfLesson> lessons;
  final ValueChanged<PdfLesson> onOpen;

  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(20), children: [
        Row(children: [
          const Text('选择课文', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 12),
        for (final l in lessons) ...[
          SectionCard(
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 8),
              title: Text(l.title),
              subtitle: Text('第 ${l.startPage}~${l.endPage} 页'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => onOpen(l),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ]);
}
