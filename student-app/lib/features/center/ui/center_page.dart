import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../reader/reader_controller.dart';
import '../center_controller.dart';
import '../center_logic.dart';
import '../data/center_models.dart';
import '../../shell/task_nav.dart';
import '../speech_player.dart';

class CenterPage extends ConsumerWidget {
  const CenterPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(centerControllerProvider.select((s) => s.messageSeq), (prev, next) {
      final msg = ref.read(centerControllerProvider).message;
      if (msg != null && prev != next) showMessage(context, msg);
    });
    final s = ref.watch(centerControllerProvider);
    final ctl = ref.read(centerControllerProvider.notifier);
    return ListView(padding: const EdgeInsets.all(20), children: [
      const Text('学习中心', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
      const SizedBox(height: 12),
      SectionCard(
        padding: const EdgeInsets.all(12),
        child: ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.auto_stories, color: AppColors.blue),
          title: const Text('个性化学习', style: TextStyle(fontWeight: FontWeight.w600)),
          subtitle: const Text('选教材读原文，划词查释义、记笔记', style: TextStyle(fontSize: 12)),
          trailing: const Icon(Icons.chevron_right),
          onTap: () async {
            await ref.read(readerControllerProvider.notifier).enterCatalog();
            if (!context.mounted) return;
            context.push(taskRoute('/reader', returnTo: '/center'));
          },
        ),
      ),
      const SizedBox(height: 16),
      if (s.pending == null)
        const _HubHint()
      else
        s.material.when(
          loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
          error: (_, _) => ErrorCard(message: '材料加载失败，请检查网络或后端服务', onRetry: ctl.reload),
          data: (m) => m.isEmpty ? const _ListeningEmpty() : _MaterialView(state: s, material: m),
        ),
    ]);
  }
}

class _HubHint extends StatelessWidget {
  const _HubHint();

  @override
  Widget build(BuildContext context) => SectionCard(
        child: Column(children: [
          const Icon(Icons.home, size: 32, color: AppColors.gray),
          const SizedBox(height: 8),
          const Text(
            '英语听力练习请从「学习首页」点击今日的「听力理解」任务进入。',
            style: TextStyle(color: AppColors.gray, height: 1.5),
          ),
        ]),
      );
}

class _ListeningEmpty extends StatelessWidget {
  const _ListeningEmpty();

  @override
  Widget build(BuildContext context) => SectionCard(
        child: Column(children: [
          const Icon(Icons.headphones, size: 32, color: AppColors.gray),
          const SizedBox(height: 8),
          const Text('暂无听力材料，请让家长重新生成本日任务', style: TextStyle(color: AppColors.gray)),
        ]),
      );
}

class _MaterialView extends ConsumerWidget {
  const _MaterialView({required this.state, required this.material});

  final CenterState state;
  final CenterMaterial material;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SectionCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('听力对话', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: () => ref.read(speechPlayerProvider).speak(material.text).catchError((Object _) {
              if (context.mounted) showMessage(context, '播放失败，请稍后重试');
            }),
            icon: const Icon(Icons.play_arrow),
            label: const Text('播放对话'),
          ),
          const SizedBox(height: 6),
          const Text('认真听，不要看文本哦', style: TextStyle(color: AppColors.gray)),
        ]),
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < material.questions.length; i++) ...[
        _QuestionCard(
          index: i,
          question: material.questions[i],
          result: state.results[i],
          input: state.inputs[i],
          listeningMode: true,
        ),
        const SizedBox(height: 12),
      ],
      if (_canRetrySubmit)
        FilledButton.icon(
          onPressed: ref.read(centerControllerProvider.notifier).retrySubmit,
          icon: const Icon(Icons.refresh),
          label: const Text('重新提交'),
        ),
    ]);
  }

  bool get _canRetrySubmit =>
      state.submitFailed &&
      !state.submitting &&
      state.pending != null &&
      state.results.isNotEmpty &&
      state.results.every((r) => r != null);
}

class _QuestionCard extends ConsumerStatefulWidget {
  const _QuestionCard({
    required this.index,
    required this.question,
    required this.result,
    required this.input,
    this.listeningMode = false,
  });

  final int index;
  final CenterQuestion question;
  final bool? result;
  final String input;
  final bool listeningMode;

  @override
  ConsumerState<_QuestionCard> createState() => _QuestionCardState();
}

class _QuestionCardState extends ConsumerState<_QuestionCard> {
  TextEditingController? _ctl;

  TextEditingController get _textCtl => _ctl ??= TextEditingController(text: widget.input);

  @override
  void dispose() {
    _ctl?.dispose();
    super.dispose();
  }

  void _submitText() {
    if (_textCtl.text.trim().isEmpty) return;
    ref.read(centerControllerProvider.notifier).answer(widget.index, text: _textCtl.text);
  }

  void _pickOption(int i) {
    ref.read(centerControllerProvider.notifier).answer(widget.index, selectedIndex: i);
  }

  String get _revealedAnswer {
    final q = widget.question;
    if (q.isMultipleChoice && q.correctIndex != null) return q.options[q.correctIndex!];
    return q.answer;
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.question;
    final mc = widget.listeningMode ? q.options.length >= 4 : q.isMultipleChoice;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${widget.index + 1}. ${q.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (widget.result == null)
          if (mc)
            Column(
              children: [
                for (var i = 0; i < q.options.length; i++)
                  RadioListTile<int>(
                    key: ValueKey('option-${widget.index}-$i'),
                    contentPadding: EdgeInsets.zero,
                    title: Text(q.options[i]),
                    value: i,
                    groupValue: null,
                    onChanged: (_) => _pickOption(i),
                  ),
              ],
            )
          else
            Row(children: [
              Expanded(
                child: TextField(
                  key: ValueKey('answer-${widget.index}'),
                  controller: _textCtl,
                  decoration: const InputDecoration(hintText: '输入你的答案', isDense: true, border: OutlineInputBorder()),
                  textInputAction: TextInputAction.done,
                  onChanged: (v) => ref.read(centerControllerProvider.notifier).setInput(widget.index, v),
                  onSubmitted: (_) => _submitText(),
                ),
              ),
              const SizedBox(width: 8),
              ValueListenableBuilder<TextEditingValue>(
                valueListenable: _textCtl,
                builder: (context, v, _) => FilledButton(
                  key: ValueKey('submit-${widget.index}'),
                  onPressed: v.text.trim().isEmpty ? null : _submitText,
                  child: const Text('提交'),
                ),
              ),
            ])
        else
          Text(
            '${widget.result! ? '✓' : '✗'} 答案：$_revealedAnswer',
            style: TextStyle(color: widget.result! ? AppColors.green : Colors.red, fontWeight: FontWeight.w600),
          ),
      ]),
    );
  }
}
