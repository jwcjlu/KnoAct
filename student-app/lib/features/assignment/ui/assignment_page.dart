import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_page_app_bar.dart';
import '../assignment_controller.dart';
import '../data/assignment_models.dart';

class AssignmentPage extends ConsumerWidget {
  const AssignmentPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(assignmentControllerProvider);
    final ctl = ref.read(assignmentControllerProvider.notifier);
    return Scaffold(
      appBar: const TaskPageAppBar(title: '本课作业'),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        if (s.busy)
          _BusyCard(label: s.busyLabel ?? '请稍候…')
        else if (s.result != null)
          _ResultView(state: s, ctl: ctl)
        else if (s.questions.isNotEmpty)
          _QuestionList(state: s, ctl: ctl)
        else
          _IdleCard(onStart: ctl.generate),
      ]),
    );
  }
}

class _BusyCard extends StatelessWidget {
  const _BusyCard({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) => SectionCard(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 24),
          child: Column(children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 12),
            Text(label, style: const TextStyle(color: AppColors.gray)),
          ]),
        ),
      );
}

class _IdleCard extends StatelessWidget {
  const _IdleCard({required this.onStart});

  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) => SectionCard(
        child: Column(children: [
          const Icon(Icons.edit_note, size: 40, color: AppColors.blue),
          const SizedBox(height: 8),
          const Text('读完课文后做几道理解题', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          const Text('正确率达到及格线才算学完本课', style: TextStyle(color: AppColors.gray)),
          const SizedBox(height: 16),
          FilledButton.icon(onPressed: onStart, icon: const Icon(Icons.play_arrow), label: const Text('去做作业')),
        ]),
      );
}

class _QuestionList extends ConsumerWidget {
  const _QuestionList({required this.state, required this.ctl});

  final AssignmentState state;
  final AssignmentController ctl;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final allAnswered = state.inputs.every((i) => i.trim().isNotEmpty);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('第 ${state.round} 组', style: const TextStyle(color: AppColors.gray, fontSize: 13)),
      const SizedBox(height: 8),
      for (var i = 0; i < state.questions.length; i++) ...[
        SectionCard(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${i + 1}. ${state.questions[i].question}', style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            TextField(
              key: ValueKey('assignment-answer-$i'),
              decoration: const InputDecoration(hintText: '写下你的回答…', isDense: true, border: OutlineInputBorder()),
              onChanged: (v) => ctl.setInput(i, v),
            ),
          ]),
        ),
        const SizedBox(height: 12),
      ],
      const SizedBox(height: 4),
      FilledButton(
        onPressed: allAnswered ? ctl.submit : null,
        child: const Text('提交作业'),
      ),
      const SizedBox(height: 8),
      OutlinedButton(onPressed: ctl.cancel, child: const Text('先不做了')),
    ]);
  }
}

class _ResultView extends ConsumerWidget {
  const _ResultView({required this.state, required this.ctl});

  final AssignmentState state;
  final AssignmentController ctl;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = state.result!;
    final pct = (r.rate * 100).round();
    final linePct = (r.threshold * 100).round();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SectionCard(
        child: Column(children: [
          Icon(r.passed ? Icons.check_circle : Icons.cancel, size: 40, color: r.passed ? AppColors.green : Colors.red),
          const SizedBox(height: 8),
          Text(
            r.passed ? '本课学习完成' : '本组还没达到 $linePct%',
            style: TextStyle(fontWeight: FontWeight.w700, color: r.passed ? AppColors.green : Colors.red),
          ),
          const SizedBox(height: 4),
          Text(
            '答对 ${r.correct} / ${r.total} 题（$pct%），${r.passed ? '课程进度已更新' : '看看正确答案再做一组'}',
            style: const TextStyle(color: AppColors.gray),
          ),
        ]),
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < r.items.length; i++) ...[
        _GradeItem(index: i, item: r.items[i]),
        const SizedBox(height: 8),
      ],
      const SizedBox(height: 8),
      FilledButton(
        onPressed: ctl.generate,
        child: Text(r.passed ? '再练一组' : '继续做下一组'),
      ),
    ]);
  }
}

class _GradeItem extends StatelessWidget {
  const _GradeItem({required this.index, required this.item});

  final int index;
  final AssignmentGradeItem item;

  @override
  Widget build(BuildContext context) {
    final color = item.isCorrect ? AppColors.green : Colors.red;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${item.isCorrect ? '✓' : '✗'} ', style: TextStyle(color: color, fontWeight: FontWeight.w700)),
          Expanded(child: Text('${index + 1}. ${item.question}', style: const TextStyle(fontWeight: FontWeight.w600))),
        ]),
        const SizedBox(height: 6),
        Text('你的回答：${item.studentAnswer.isEmpty ? '（未作答）' : item.studentAnswer}', style: TextStyle(color: color)),
        if (!item.isCorrect) ...[
          const SizedBox(height: 2),
          Text('正确答案：${item.answer}', style: const TextStyle(color: AppColors.green)),
        ],
        if (item.feedback.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(item.feedback, style: const TextStyle(color: AppColors.gray)),
        ],
      ]),
    );
  }
}
