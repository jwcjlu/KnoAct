import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../lesson_audio_controller.dart';
import 'audio_bar.dart';

/// 磨耳朵：列教材 → Unit 音频 → 播放/循环。
class ListeningPage extends ConsumerWidget {
  const ListeningPage({super.key, required this.documentId});
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
          return ListView(children: [
            for (final a in rows) AudioBar(audio: a, url: repo.audioUrl(a.audioPath)),
          ]);
        },
      ),
    );
  }
}
