import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../ask/ask_controller.dart';
import '../../ask/ui/ask_panel.dart';
import '../../assignment/assignment_controller.dart';
import '../../reader/reader_controller.dart';
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
      SectionCard(
        padding: const EdgeInsets.all(12),
        child: ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.auto_stories, color: AppColors.blue),
          title: const Text('个性化学习', style: TextStyle(fontWeight: FontWeight.w600)),
          subtitle: const Text('选教材读原文，划词查释义、记笔记', style: TextStyle(fontSize: 12)),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {
            ref.read(readerControllerProvider.notifier).loadDocuments();
            context.go('/reader');
          },
        ),
      ),
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
                  onPressed: () => ref.read(speechPlayerProvider).speak(material.text).catchError((Object _) {
                    if (context.mounted) showMessage(context, '播放失败，请稍后重试');
                  }),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('播放对话'),
                ),
                const SizedBox(height: 6),
                const Text('认真听，不要看文本哦', style: TextStyle(color: AppColors.gray)),
              ])
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('阅读课文', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                _ReadingView(material: material),
              ]),
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < material.questions.length; i++) ...[
        _QuestionCard(index: i, question: material.questions[i], result: state.results[i], input: state.inputs[i]),
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
      state.pending?.tab == state.tab &&
      state.results.isNotEmpty &&
      state.results.every((r) => r != null);
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

  void _submit() {
    if (_ctl.text.trim().isEmpty) return;
    ref.read(centerControllerProvider.notifier).answer(widget.index, _ctl.text);
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
                textInputAction: TextInputAction.done,
                onChanged: (v) => ref.read(centerControllerProvider.notifier).setInput(widget.index, v),
                onSubmitted: (_) => _submit(),
              ),
            ),
            const SizedBox(width: 8),
            ValueListenableBuilder<TextEditingValue>(
              valueListenable: _ctl,
              builder: (context, v, _) => FilledButton(
                key: ValueKey('submit-${widget.index}'),
                onPressed: v.text.trim().isEmpty ? null : _submit,
                child: const Text('提交'),
              ),
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

class _ReadingView extends ConsumerStatefulWidget {
  const _ReadingView({required this.material});

  final CenterMaterial material;

  @override
  ConsumerState<_ReadingView> createState() => _ReadingViewState();
}

class _ReadingViewState extends ConsumerState<_ReadingView> {
  int? _selected;
  bool _chatOpen = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _initAsk();
    });
  }

  void _initAsk() {
    final lessonId = widget.material.lessonId;
    if (lessonId == null) return;
    ref.read(askControllerProvider.notifier).init(lessonId: lessonId, context: widget.material.text);
  }

  void _select(int i, List<String> sentences) {
    setState(() {
      _selected = _selected == i ? null : i;
      final sentence = _selected == null ? '' : sentences[i];
      ref.read(askControllerProvider.notifier).setSelected(sentence);
      // 选中句子即展开对话栏，就地提问
      _chatOpen = true;
    });
  }

  void _doAssignment() {
    final lessonId = widget.material.lessonId;
    if (lessonId == null) return;
    ref.read(assignmentControllerProvider.notifier).init(lessonId: lessonId, subject: '语文');
    context.go('/assignment');
  }

  @override
  Widget build(BuildContext context) {
    final sentences = splitSentences(widget.material.text);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      // 课文文本（点句选中，成为对话引用）
      Text.rich(
        TextSpan(
          children: [
            for (var i = 0; i < sentences.length; i++)
              WidgetSpan(
                child: GestureDetector(
                  onTap: () => _select(i, sentences),
                  child: Text(
                    sentences[i],
                    style: TextStyle(
                      height: 1.7,
                      backgroundColor: _selected == i ? AppColors.blueSoft : null,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
      const SizedBox(height: 4),
      const Text('点选句子，可就它提问', style: TextStyle(color: AppColors.gray, fontSize: 12)),
      const SizedBox(height: 12),
      if (_chatOpen)
        const AskPanel()
      else
        FilledButton.icon(
          key: const ValueKey('open-ask'),
          onPressed: () => setState(() => _chatOpen = true),
          icon: const Icon(Icons.auto_awesome, size: 18),
          label: const Text('问问 AI'),
        ),
      const SizedBox(height: 12),
      OutlinedButton.icon(
        key: const ValueKey('do-assignment'),
        onPressed: _doAssignment,
        icon: const Icon(Icons.edit_note, size: 18),
        label: const Text('本课作业'),
      ),
    ]);
  }
}
