import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../math_controller.dart';
import '../data/math_repository.dart';

class MathPage extends ConsumerWidget {
  const MathPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(mathControllerProvider);
    final ctl = ref.read(mathControllerProvider.notifier);
    return Scaffold(
      appBar: AppBar(title: Text(s.title.isEmpty ? '数学练习' : s.title), backgroundColor: AppColors.bg, scrolledUnderElevation: 0),
      body: s.questions.isEmpty
          ? const Center(child: Text('本次数学练习暂无题目', style: TextStyle(color: AppColors.gray)))
          : ListView(padding: const EdgeInsets.all(20), children: [
              if (s.result == null)
                Text('已作答 ${s.answers.where((a) => a.trim().isNotEmpty).length} / ${s.questions.length}',
                    style: const TextStyle(color: AppColors.gray, fontSize: 13)),
              const SizedBox(height: 12),
              for (var i = 0; i < s.questions.length; i++) ...[
                _MathCard(
                  index: i,
                  question: s.questions[i],
                  answer: s.answers[i],
                  result: s.result?.results[i],
                  onChanged: (v) => ctl.setAnswer(i, v),
                ),
                const SizedBox(height: 12),
              ],
              if (s.result == null)
                FilledButton(
                  onPressed: s.busy || s.answers.any((a) => a.trim().isEmpty) ? null : ctl.submit,
                  child: Text(s.busy ? '正在判分…' : '提交答案'),
                )
              else
                _ResultFooter(result: s.result!),
            ]),
    );
  }
}

class _MathCard extends StatelessWidget {
  const _MathCard({required this.index, required this.question, required this.answer, required this.result, required this.onChanged});

  final int index;
  final MathQuestion question;
  final String answer;
  final bool? result;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final res = result;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${index + 1}. ${question.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (res == null)
          TextField(
            key: ValueKey('math-answer-$index'),
            decoration: const InputDecoration(hintText: '输入答案（只写数字）', isDense: true, border: OutlineInputBorder()),
            keyboardType: TextInputType.number,
            onChanged: onChanged,
          )
        else
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('你的答案：$answer', style: TextStyle(color: res ? AppColors.green : Colors.red, fontWeight: FontWeight.w600)),
            if (!res) Text('正确答案：${question.answer}', style: const TextStyle(color: AppColors.green)),
          ]),
      ]),
    );
  }
}

class _ResultFooter extends StatelessWidget {
  const _ResultFooter({required this.result});

  final MathGradeResult result;

  @override
  Widget build(BuildContext context) {
    final wrong = result.total - result.correct;
    return SectionCard(
      child: Column(children: [
        const Icon(Icons.check_circle, size: 40, color: AppColors.green),
        const SizedBox(height: 8),
        const Text('练习完成！', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text('正确 ${result.correct}', style: const TextStyle(color: AppColors.green, fontWeight: FontWeight.w700)),
          const SizedBox(width: 24),
          Text('错误 $wrong', style: TextStyle(color: wrong > 0 ? Colors.red : AppColors.gray, fontWeight: FontWeight.w700)),
        ]),
      ]),
    );
  }
}
