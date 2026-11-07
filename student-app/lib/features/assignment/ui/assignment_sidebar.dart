import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../assignment_controller.dart';
import '../data/assignment_models.dart';

/// 阅读页右栏「本课作业」卡片（对齐 Web `im-assign`）
class AssignmentSidebar extends ConsumerWidget {
  const AssignmentSidebar({super.key, this.lessonTitle});

  final String? lessonTitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(assignmentControllerProvider);
    final ctl = ref.read(assignmentControllerProvider.notifier);
    return SectionCard(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Icon(Icons.edit_note, size: 18, color: AppColors.blue),
          const SizedBox(width: 6),
          const Text('本课作业', style: TextStyle(fontWeight: FontWeight.w700)),
          if (s.round > 0) ...[
            const SizedBox(width: 8),
            Text('第 ${s.round} 组', style: const TextStyle(fontSize: 12, color: AppColors.gray)),
          ],
          if (lessonTitle != null && lessonTitle!.isNotEmpty) ...[
            const Spacer(),
            Flexible(
              child: Text(
                lessonTitle!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: AppColors.gray),
              ),
            ),
          ],
        ]),
        const SizedBox(height: 10),
        if (s.busy)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
              const SizedBox(width: 10),
              Text(s.busyLabel ?? '请稍候…', style: const TextStyle(color: AppColors.gray, fontSize: 13)),
            ]),
          )
        else if (s.result != null)
          _ResultBlock(state: s, ctl: ctl)
        else if (s.questions.isNotEmpty)
          _QuestionsBlock(state: s, ctl: ctl)
        else
          _IdleBlock(onStart: ctl.generate),
      ]),
    );
  }
}

class _IdleBlock extends StatelessWidget {
  const _IdleBlock({required this.onStart});

  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text(
          '读完课文后做几道理解题，正确率达到及格线才算学完本课。',
          style: TextStyle(fontSize: 13, color: AppColors.gray, height: 1.45),
        ),
        const SizedBox(height: 12),
        FilledButton(onPressed: onStart, child: const Text('去做作业')),
      ]);
}

class _QuestionsBlock extends ConsumerWidget {
  const _QuestionsBlock({required this.state, required this.ctl});

  final AssignmentState state;
  final AssignmentController ctl;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final allAnswered = state.inputs.every((i) => i.trim().isNotEmpty);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('做作业期间 AI 对话已暂停', style: TextStyle(fontSize: 12, color: AppColors.gray)),
      const SizedBox(height: 10),
      for (var i = 0; i < state.questions.length; i++) ...[
        Text('${i + 1}. ${state.questions[i].question}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        const SizedBox(height: 6),
        TextField(
          key: ValueKey('reader-assignment-$i'),
          decoration: const InputDecoration(hintText: '写下你的回答…', isDense: true, border: OutlineInputBorder()),
          onChanged: (v) => ctl.setInput(i, v),
        ),
        const SizedBox(height: 10),
      ],
      FilledButton(onPressed: allAnswered ? ctl.submit : null, child: const Text('提交作业')),
      const SizedBox(height: 6),
      TextButton(onPressed: ctl.cancel, child: const Text('先不做了')),
    ]);
  }
}

class _ResultBlock extends ConsumerWidget {
  const _ResultBlock({required this.state, required this.ctl});

  final AssignmentState state;
  final AssignmentController ctl;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = state.result!;
    final pct = (r.rate * 100).round();
    final linePct = (r.threshold * 100).round();
    final passed = r.passed;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(
        passed ? '✓ 本课学习完成' : '✕ 本组还没达到 $linePct%',
        style: TextStyle(fontWeight: FontWeight.w700, color: passed ? AppColors.green : Colors.red, fontSize: 14),
      ),
      const SizedBox(height: 4),
      Text(
        '答对 ${r.correct} / ${r.total} 题（$pct%）',
        style: const TextStyle(fontSize: 13, color: AppColors.gray),
      ),
      const SizedBox(height: 8),
      for (var i = 0; i < r.items.length; i++) _CompactGradeItem(index: i, item: r.items[i]),
      const SizedBox(height: 8),
      FilledButton(
        onPressed: ctl.generate,
        child: Text(passed ? '再练一组' : '继续做下一组'),
      ),
      if (!passed) ...[
        const SizedBox(height: 4),
        TextButton(onPressed: ctl.cancel, child: const Text('先不做了')),
      ],
    ]);
  }
}

class _CompactGradeItem extends StatelessWidget {
  const _CompactGradeItem({required this.index, required this.item});

  final int index;
  final AssignmentGradeItem item;

  @override
  Widget build(BuildContext context) {
    final color = item.isCorrect ? AppColors.green : Colors.red;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${item.isCorrect ? '✓' : '✗'} ${index + 1}. ${item.question}',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
        if (!item.isCorrect)
          Text('正确答案：${item.answer}', style: const TextStyle(fontSize: 12, color: AppColors.green)),
      ]),
    );
  }
}

/// 作业进行中（已出题、尚未达标）时暂停 AI 对话
bool assignmentBlocksChat(AssignmentState s) => s.questions.isNotEmpty && !(s.result?.passed ?? false);
