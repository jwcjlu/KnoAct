import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../reader/data/pdf_repository.dart';
import '../lesson_audio_controller.dart';
import '../models/lesson_audio.dart';
import 'audio_bar.dart';

/// 磨耳朵：先选教材 → 列该教材的 Unit 音频 → 播放/循环。
class ListeningPage extends ConsumerStatefulWidget {
  const ListeningPage({super.key, this.initialDocumentId});
  final int? initialDocumentId;

  @override
  ConsumerState<ListeningPage> createState() => _ListeningPageState();
}

class _ListeningPageState extends ConsumerState<ListeningPage> {
  @override
  Widget build(BuildContext context) {
    final docId = widget.initialDocumentId;
    if (docId != null) {
      return _AudioListView(documentId: docId);
    }
    return const _DocumentListView();
  }
}

/// 教材列表：加载当前孩子绑定的教材，点击进入该教材的音频列表。
class _DocumentListView extends ConsumerStatefulWidget {
  const _DocumentListView();

  @override
  ConsumerState<_DocumentListView> createState() => _DocumentListViewState();
}

class _DocumentListViewState extends ConsumerState<_DocumentListView> {
  late final Future<List<PdfDoc>> _docsFuture;

  @override
  void initState() {
    super.initState();
    _docsFuture = ref.read(pdfRepositoryProvider).documents();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('磨耳朵')),
      body: FutureBuilder<List<PdfDoc>>(
        future: _docsFuture,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('加载失败：${snap.error}'));
          }
          final docs = snap.data ?? const <PdfDoc>[];
          if (docs.isEmpty) {
            return const Center(child: Text('还没有绑定教材'));
          }
          return ListView.separated(
            itemCount: docs.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final doc = docs[i];
              return ListTile(
                title: Text(doc.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text(doc.subject),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => _AudioListView(documentId: doc.id),
                  ));
                },
              );
            },
          );
        },
      ),
    );
  }
}

/// 单个教材的音频列表：加载该教材的 Unit 音频并逐条渲染 AudioBar。
class _AudioListView extends ConsumerWidget {
  const _AudioListView({required this.documentId});

  final int documentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(lessonAudioProvider(documentId));
    return Scaffold(
      appBar: AppBar(title: const Text('磨耳朵')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('加载失败：$e')),
        data: (rows) {
          if (rows.isEmpty) {
            return const Center(child: Text('该教材还没有配套音频'));
          }
          final repo = ref.read(lessonAudioRepositoryProvider);
          final (unit, wordList) = splitAudioRows(rows);
          return ListView(children: [
            for (final a in unit) AudioBar(audio: a, url: repo.audioUrl(a.audioPath)),
            if (wordList.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 20, 16, 8),
                child: Text('单词表', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
              ),
              for (final a in wordList) AudioBar(audio: a, url: repo.audioUrl(a.audioPath)),
            ],
          ]);
        },
      ),
    );
  }
}
