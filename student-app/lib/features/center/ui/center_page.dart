import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../center_controller.dart';
import '../center_logic.dart';
import '../data/center_models.dart';
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
      SegmentedButton<CenterTab>(
        segments: [
          for (final t in CenterTab.values)
            ButtonSegment(
              value: t,
              label: Text(t.label),
              icon: Icon(t == CenterTab.listening ? Icons.headphones : Icons.menu_book),
            ),
        ],
        selected: {s.tab},
        onSelectionChanged: (v) => ctl.selectTab(v.first),
      ),
      const SizedBox(height: 16),
      s.material.when(
        loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
        error: (_, _) => ErrorCard(message: '材料加载失败，请检查网络或后端服务', onRetry: ctl.reload),
        data: (m) => m.isEmpty ? _Empty(tab: s.tab) : _MaterialView(state: s, material: m),
      ),
    ]);
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.tab});

  final CenterTab tab;

  @override
  Widget build(BuildContext context) => SectionCard(
        child: Column(children: [
          Icon(tab == CenterTab.listening ? Icons.headphones : Icons.menu_book, size: 32, color: AppColors.gray),
          const SizedBox(height: 8),
          Text(
            tab == CenterTab.listening ? '暂无听力材料，AI 将根据学习进度生成对话' : '暂无阅读材料，请在家长端导入教材',
            style: const TextStyle(color: AppColors.gray),
          ),
        ]),
      );
}

class _MaterialView extends ConsumerWidget {
  const _MaterialView({required this.state, required this.material});

  final CenterState state;
  final CenterMaterial material;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final listening = state.tab == CenterTab.listening;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SectionCard(
        child: listening
            ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('听力对话', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () => ref.read(speechPlayerProvider).speak(material.text),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('播放对话'),
                ),
                const SizedBox(height: 6),
                const Text('认真听，不要看文本哦', style: TextStyle(color: AppColors.gray)),
              ])
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('阅读课文', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                Text(material.text, style: const TextStyle(height: 1.7)),
              ]),
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < material.questions.length; i++) ...[
        _QuestionCard(index: i, question: material.questions[i], result: state.results[i], input: state.inputs[i]),
        const SizedBox(height: 12),
      ],
    ]);
  }
}

class _QuestionCard extends ConsumerStatefulWidget {
  const _QuestionCard({required this.index, required this.question, required this.result, required this.input});

  final int index;
  final CenterQuestion question;
  final bool? result;
  final String input;

  @override
  ConsumerState<_QuestionCard> createState() => _QuestionCardState();
}

class _QuestionCardState extends ConsumerState<_QuestionCard> {
  late final TextEditingController _ctl = TextEditingController(text: widget.input);

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.question;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${widget.index + 1}. ${q.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (widget.result == null)
          Row(children: [
            Expanded(
              child: TextField(
                key: ValueKey('answer-${widget.index}'),
                controller: _ctl,
                decoration: const InputDecoration(hintText: '输入你的答案', isDense: true, border: OutlineInputBorder()),
                onChanged: (v) => ref.read(centerControllerProvider.notifier).setInput(widget.index, v),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              key: ValueKey('submit-${widget.index}'),
              onPressed: () => ref.read(centerControllerProvider.notifier).answer(widget.index, _ctl.text),
              child: const Text('提交'),
            ),
          ])
        else
          Text(
            '${widget.result! ? '✓' : '✗'} 答案：${q.answer}',
            style: TextStyle(color: widget.result! ? AppColors.green : Colors.red, fontWeight: FontWeight.w600),
          ),
      ]),
    );
  }
}
