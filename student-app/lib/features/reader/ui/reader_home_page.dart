import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_nav.dart';
import '../../shell/task_page_app_bar.dart';
import '../reader_controller.dart';
import '../data/pdf_repository.dart';

/// 个性化学习入口：教材列表 → 选课 → 进入阅读
class ReaderHomePage extends ConsumerWidget {
  const ReaderHomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(readerControllerProvider);
    final ctl = ref.read(readerControllerProvider.notifier);
    final returnTo = returnToFromState(context);
    final body = s.lessons.isNotEmpty
        ? _LessonList(
            lessons: s.lessons,
            onBackToDocuments: () => ctl.backToDocumentList(),
            onOpen: (l) async {
              await ctl.openLesson(l);
              if (context.mounted) {
                context.push(taskRoute('/reader/view', returnTo: returnTo));
              }
            },
          )
        : s.documents.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => ErrorCard(message: '教材加载失败，请检查网络或后端服务', onRetry: ctl.loadDocuments),
            data: (docs) => docs.isEmpty
                ? const Center(child: Text('暂无教材，请在家长端上传 PDF', style: TextStyle(color: AppColors.gray)))
                : _DocumentList(
                    docs: docs,
                    onSelect: (doc) async {
                      await ctl.loadLessons(doc.id, subject: doc.subject);
                      if (!context.mounted) return;
                      if (ref.read(readerControllerProvider).lessons.isEmpty) {
                        showMessage(context, '该教材暂无课文');
                      }
                    },
                  ),
          );

  // Web 上 Scaffold.appBar 有时不渲染操作按钮；顶栏嵌在 body 内保证 ← / 首页 可见
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TaskPageNavRow(title: '个性化学习', returnTo: returnTo),
            Expanded(child: body),
          ],
        ),
      ),
    );
  }
}

class _DocumentList extends StatelessWidget {
  const _DocumentList({required this.docs, required this.onSelect});

  final List<PdfDoc> docs;
  final Future<void> Function(PdfDoc doc) onSelect;

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
              onTap: () => onSelect(d),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ]);
}

class _LessonList extends StatelessWidget {
  const _LessonList({required this.lessons, required this.onOpen, required this.onBackToDocuments});

  final List<PdfLesson> lessons;
  final ValueChanged<PdfLesson> onOpen;
  final VoidCallback onBackToDocuments;

  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(20), children: [
        Row(
          children: [
            const Expanded(
              child: Text('选择课文', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
            ),
            TextButton.icon(
              onPressed: onBackToDocuments,
              icon: const Icon(Icons.menu_book_outlined, size: 20),
              label: const Text('换教材'),
            ),
          ],
        ),
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
