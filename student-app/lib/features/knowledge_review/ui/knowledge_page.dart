import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_page_app_bar.dart';
import '../knowledge_controller.dart';
import '../data/knowledge_repository.dart';

class KnowledgePage extends ConsumerWidget {
  const KnowledgePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(knowledgeControllerProvider);
    final ctl = ref.read(knowledgeControllerProvider.notifier);
    final allGraded = s.results.every((r) => r != null);
    return Scaffold(
      appBar: TaskPageAppBar(title: s.title.isEmpty ? '基础知识' : s.title),
      body: s.points.isEmpty
          ? const Center(child: Text('本次任务暂无知识点', style: TextStyle(color: AppColors.gray)))
          : ListView(padding: const EdgeInsets.all(20), children: [
              if (!allGraded)
                Text('已作答 ${s.inputs.where((i) => i.trim().isNotEmpty).length} / ${s.points.length}',
                    style: const TextStyle(color: AppColors.gray, fontSize: 13)),
              const SizedBox(height: 12),
              for (var i = 0; i < s.points.length; i++) ...[
                _KnowledgeCard(
                  index: i,
                  point: s.points[i],
                  input: s.inputs[i],
                  result: s.results[i],
                  onChanged: (v) => ctl.setInput(i, v),
                ),
                const SizedBox(height: 12),
              ],
              if (!allGraded)
                FilledButton(
                  onPressed: s.busy || s.inputs.any((i) => i.trim().isEmpty) ? null : ctl.submit,
                  child: Text(s.busy ? '正在判分…' : '提交答案'),
                )
              else
                _KnowledgeFooter(correct: s.results.where((r) => r == true).length, total: s.points.length),
            ]),
    );
  }
}

class _KnowledgeCard extends StatelessWidget {
  const _KnowledgeCard({required this.index, required this.point, required this.input, required this.result, required this.onChanged});

  final int index;
  final KnowledgePoint point;
  final String input;
  final bool? result;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final res = result;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (point.category.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: AppColors.greenSoft, borderRadius: BorderRadius.circular(6)),
              child: Text(point.category, style: const TextStyle(fontSize: 12, color: AppColors.green, fontWeight: FontWeight.w600)),
            ),
          Expanded(child: Text('${index + 1}. ${point.display}', style: const TextStyle(fontWeight: FontWeight.w600))),
        ]),
        const SizedBox(height: 8),
        if (res == null)
          TextField(
            key: ValueKey('knowledge-answer-$index'),
            decoration: const InputDecoration(hintText: '写下你的回答…', isDense: true, border: OutlineInputBorder()),
            onChanged: onChanged,
          )
        else
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('你的回答：$input', style: TextStyle(color: res ? AppColors.green : Colors.red)),
            if (!res && point.answer.isNotEmpty) Text('参考答案：${point.answer}', style: const TextStyle(color: AppColors.green)),
          ]),
      ]),
    );
  }
}

class _KnowledgeFooter extends StatelessWidget {
  const _KnowledgeFooter({required this.correct, required this.total});

  final int correct;
  final int total;

  @override
  Widget build(BuildContext context) {
    final wrong = total - correct;
    return SectionCard(
      child: Column(children: [
        const Icon(Icons.check_circle, size: 40, color: AppColors.green),
        const SizedBox(height: 8),
        const Text('复习完成！', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text('正确 $correct', style: const TextStyle(color: AppColors.green, fontWeight: FontWeight.w700)),
          const SizedBox(width: 24),
          Text('需加强 $wrong', style: TextStyle(color: wrong > 0 ? Colors.red : AppColors.gray, fontWeight: FontWeight.w700)),
        ]),
      ]),
    );
  }
}
