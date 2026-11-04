import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../wrongbook_controller.dart';
import '../data/wrongbook_models.dart';

const _subjects = ['全部', '语文', '英语', '数学'];

class WrongbookPage extends ConsumerWidget {
  const WrongbookPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(wrongbookControllerProvider);
    final ctl = ref.read(wrongbookControllerProvider.notifier);
    return RefreshIndicator(
      onRefresh: ctl.reload,
      child: ListView(padding: const EdgeInsets.all(20), children: [
        const Text('智能错题本', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        const Text('练习中的错题会自动收录，标记掌握后移出复习', style: TextStyle(color: AppColors.gray)),
        const SizedBox(height: 16),
        Wrap(spacing: 8, children: [
          for (final sub in _subjects)
            ChoiceChip(
              key: ValueKey('wrongbook-subject-$sub'),
              selected: s.subject == sub,
              onSelected: (_) => ctl.setSubject(sub),
              label: Text(sub),
            ),
        ]),
        const SizedBox(height: 16),
        s.mistakes.when(
          loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
          error: (_, _) => ErrorCard(message: '错题加载失败，请检查网络或后端服务', onRetry: ctl.reload),
          data: (list) => list.isEmpty ? const _Empty() : Column(children: [for (final m in list) _MistakeCard(item: m)]),
        ),
      ]),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 48),
        child: Center(
          child: Column(children: [
            Icon(Icons.check_circle_outline, size: 48, color: AppColors.green),
            SizedBox(height: 12),
            Text('当前错题都掌握了', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
            SizedBox(height: 4),
            Text('继续保持，新的错题会自动出现在这里', style: TextStyle(color: AppColors.gray)),
          ]),
        ),
      );
}

class _MistakeCard extends ConsumerWidget {
  const _MistakeCard({required this.item});

  final MistakeItem item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final subject = mistakeSubject(item.sourceType);
    final srcName = mistakeSourceNames[item.sourceType] ?? item.sourceType;
    final marking = ref.watch(wrongbookControllerProvider).markingId == item.id;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: subject == '语文' ? AppColors.blueSoft : AppColors.orangeSoft,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(subject, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: subject == '语文' ? AppColors.blue : AppColors.orange)),
          ),
          const SizedBox(width: 8),
          Text(srcName, style: const TextStyle(color: AppColors.gray, fontSize: 13)),
          const Spacer(),
          Text('已复习 ${item.consecutiveCorrect} 次', style: const TextStyle(color: AppColors.gray, fontSize: 12)),
        ]),
        const SizedBox(height: 10),
        Text(item.question, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 10),
        _AnswerRow(label: '你的答案', value: item.yourAnswer, isWrong: true),
        const SizedBox(height: 6),
        _AnswerRow(label: '正确答案', value: item.correctAnswer, isWrong: false),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: FilledButton.tonal(
            key: ValueKey('mistake-master-${item.id}'),
            onPressed: marking ? null : () => ref.read(wrongbookControllerProvider.notifier).markMastered(item.id),
            child: marking
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('标记已掌握'),
          ),
        ),
      ]),
    );
  }
}

class _AnswerRow extends StatelessWidget {
  const _AnswerRow({required this.label, required this.value, required this.isWrong});

  final String label;
  final String value;
  final bool isWrong;

  @override
  Widget build(BuildContext context) {
    final color = isWrong ? Colors.red : AppColors.green;
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(width: 64, child: Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600))),
      Expanded(child: Text(value.isEmpty ? '（空）' : value, style: TextStyle(color: isWrong ? Colors.red : AppColors.green))),
    ]);
  }
}
