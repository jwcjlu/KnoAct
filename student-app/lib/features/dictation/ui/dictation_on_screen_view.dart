import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../center/speech_player.dart';
import '../dictation_controller.dart';
import '../handwriting_pad.dart';

/// 屏上手写逐词听写（家长配置 `on_screen`）
class DictationOnScreenView extends ConsumerStatefulWidget {
  const DictationOnScreenView({super.key});

  @override
  ConsumerState<DictationOnScreenView> createState() => _DictationOnScreenViewState();
}

class _DictationOnScreenViewState extends ConsumerState<DictationOnScreenView> {
  final _padKey = GlobalKey<HandwritingPadState>();
  bool _showHint = false;

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(dictationControllerProvider);
    final ctl = ref.read(dictationControllerProvider.notifier);

    if (s.done) return _doneView(context, s);
    if (s.words.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: Text(s.title.isEmpty ? '生词听写' : s.title), backgroundColor: AppColors.bg),
        body: const Center(child: Text('当前词库暂无生词', style: TextStyle(color: AppColors.gray))),
      );
    }

    final word = s.words[s.currentIndex];
    final result = s.results[s.currentIndex];
    final isLast = s.currentIndex == s.words.length - 1;

    return Scaffold(
      appBar: AppBar(
        title: Text('${s.title.isEmpty ? '生词听写' : s.title}（${s.currentIndex + 1}/${s.words.length}）'),
        backgroundColor: AppColors.bg,
      ),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        SectionCard(
          child: Column(children: [
            FilledButton.icon(
              onPressed: () => ref.read(speechPlayerProvider).speak(word.word).catchError((Object _) {
                if (context.mounted) showMessage(context, '播放失败，请稍后重试');
              }),
              icon: const Icon(Icons.volume_up),
              label: const Text('听发音'),
            ),
            const SizedBox(height: 8),
            if (_showHint)
              Text(
                s.isEnglish ? '提示：${word.meaning}' : '提示：${word.pinyin}　${word.meaning}',
                style: const TextStyle(color: AppColors.gray),
              )
            else
              TextButton(onPressed: () => setState(() => _showHint = true), child: const Text('看提示')),
          ]),
        ),
        const SizedBox(height: 16),
        if (result == null) ...[
          const Text('在下方写出你听到的词', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          HandwritingPad(key: _padKey),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: s.busy ? null : () => _submit(),
            child: Text(s.busy ? '正在批改…' : '提交批改'),
          ),
        ] else ...[
          SectionCard(
            child: Column(children: [
              Icon(result.isCorrect ? Icons.check_circle : Icons.cancel,
                  size: 40, color: result.isCorrect ? AppColors.green : Colors.red),
              const SizedBox(height: 8),
              Text(
                result.isCorrect ? '写对了！' : '标准写法：${result.word.word}',
                style: TextStyle(fontWeight: FontWeight.w700, color: result.isCorrect ? AppColors.green : Colors.red),
              ),
              if (result.written.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text('你写的：${result.written}', style: const TextStyle(color: AppColors.gray)),
              ],
              if (!result.isCorrect) ...[
                const SizedBox(height: 8),
                TextButton(onPressed: () => ctl.appeal(s.currentIndex), child: const Text('批改有误？申诉')),
              ],
            ]),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () {
              setState(() => _showHint = false);
              ctl.next();
            },
            child: Text(isLast ? '完成听写' : '下一个词'),
          ),
        ],
      ]),
    );
  }

  Future<void> _submit() async {
    final pad = _padKey.currentState;
    if (pad == null) return;
    final base64 = await pad.exportImage();
    if (base64.isEmpty) {
      if (mounted) showMessage(context, '请先写一个字');
      return;
    }
    ref.read(dictationControllerProvider.notifier).submitHandwriting(base64);
  }

  Widget _doneView(BuildContext context, DictationState s) {
    final results = s.results.whereType<DictWordResult>().toList();
    final correct = results.where((r) => r.isCorrect).length;
    final wrong = results.length - correct;
    return Scaffold(
      appBar: AppBar(title: Text(s.title.isEmpty ? '生词听写' : s.title), backgroundColor: AppColors.bg),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(children: [
          const SizedBox(height: 24),
          const Icon(Icons.emoji_events, size: 56, color: AppColors.gold),
          const SizedBox(height: 12),
          const Text('听写完成！', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text('写对 $correct 个', style: const TextStyle(color: AppColors.green, fontWeight: FontWeight.w700)),
            const SizedBox(width: 24),
            Text('写错 $wrong 个', style: TextStyle(color: wrong > 0 ? Colors.red : AppColors.gray, fontWeight: FontWeight.w700)),
          ]),
          if (wrong > 0) ...[
            const SizedBox(height: 16),
            const Text('写错的词已收录进错题本，记得复习哦', style: TextStyle(color: AppColors.gray)),
          ],
        ]),
      ),
    );
  }
}
