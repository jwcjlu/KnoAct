import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_page_app_bar.dart';
import '../bank_exercise_controller.dart';
import '../data/bank_models.dart';
import '../passage_markup.dart';

class BankExercisePage extends ConsumerStatefulWidget {
  const BankExercisePage({
    super.key,
    required this.bankId,
    this.questionIds = const [],
    this.taskId,
  });

  final int bankId;
  final List<int> questionIds;
  final int? taskId;

  @override
  ConsumerState<BankExercisePage> createState() => _BankExercisePageState();
}

class _BankExercisePageState extends ConsumerState<BankExercisePage> {
  var _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    Future.microtask(() => ref.read(bankExerciseControllerProvider.notifier).load(
          widget.bankId,
          questionIds: widget.questionIds.isEmpty ? null : widget.questionIds,
          taskId: widget.taskId,
        ));
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(bankExerciseControllerProvider);
    final ctl = ref.read(bankExerciseControllerProvider.notifier);

    if (s.loading) {
      return const Scaffold(
        appBar: TaskPageAppBar(title: '题库练习'),
        body: Center(child: CircularProgressIndicator()),
      );
    }

  final resultByQid = {
    for (final r in (s.result?.answers ?? <BankAnswerResult>[])) r.questionId: r
  };

    return Scaffold(
      appBar: const TaskPageAppBar(title: '题库练习'),
      body: s.questions.isEmpty
          ? const Center(child: Text('本题库暂无已发布题目', style: TextStyle(color: AppColors.gray)))
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (s.error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(s.error!, style: const TextStyle(color: Colors.orange, fontSize: 13)),
                  ),
                if (s.submitted && s.result != null)
                  SectionCard(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      '得分：${s.result!.score} / ${s.result!.total}',
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: AppColors.blue),
                    ),
                  ),
                const SizedBox(height: 12),
                ..._buildQuestionBlocks(
                  questions: s.questions,
                  submitted: s.submitted,
                  resultByQid: resultByQid,
                  selectedSingle: s.selectedSingle,
                  selectedMulti: s.selectedMulti,
                  blanks: s.blanks,
                  texts: s.texts,
                  ctl: ctl,
                ),
                if (!s.submitted)
                  FilledButton(
                    onPressed: s.busy ? null : ctl.submit,
                    child: Text(s.busy ? '提交中…' : '提交答案'),
                  ),
              ],
            ),
    );
  }

  static String _firstBlank(List<String>? blanks) {
    if (blanks == null || blanks.isEmpty) return '';
    return blanks.first;
  }

  List<Widget> _buildQuestionBlocks({
    required List<BankQuestion> questions,
    required bool submitted,
    required Map<int, BankAnswerResult> resultByQid,
    required Map<int, int?> selectedSingle,
    required Map<int, List<int>> selectedMulti,
    required Map<int, List<String>> blanks,
    required Map<int, String> texts,
    required BankExerciseController ctl,
  }) {
    final shown = <int>{};
    final widgets = <Widget>[];
    for (var i = 0; i < questions.length; i++) {
      final q = questions[i];
      final pid = q.passageId;
      if (pid != null && !shown.contains(pid)) {
        shown.add(pid);
        final p = q.passage;
        if (p != null && p.content.isNotEmpty) {
          widgets.add(SectionCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('阅读材料', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.gray)),
                const SizedBox(height: 8),
                PassageContentView(title: p.title, content: p.content),
              ],
            ),
          ));
          widgets.add(const SizedBox(height: 12));
        }
      }
      widgets.add(_QuestionCard(
        index: i,
        question: q,
        submitted: submitted,
        result: resultByQid[q.id],
        selectedSingle: selectedSingle[q.id],
        selectedMulti: selectedMulti[q.id] ?? const [],
        blankText: _firstBlank(blanks[q.id]),
        textAnswer: texts[q.id] ?? '',
        onSingle: submitted ? null : (v) => ctl.setSingle(q.id, v),
        onMulti: submitted ? null : (v, on) => ctl.toggleMulti(q.id, v, on),
        onBlank: submitted ? null : (v) => ctl.setBlank(q.id, 0, v),
        onText: submitted ? null : (v) => ctl.setText(q.id, v),
      ));
      widgets.add(const SizedBox(height: 12));
    }
    return widgets;
  }
}

class _QuestionCard extends StatelessWidget {
  const _QuestionCard({
    required this.index,
    required this.question,
    required this.submitted,
    required this.result,
    required this.selectedSingle,
    required this.selectedMulti,
    required this.blankText,
    required this.textAnswer,
    required this.onSingle,
    required this.onMulti,
    required this.onBlank,
    required this.onText,
  });

  final int index;
  final BankQuestion question;
  final bool submitted;
  final BankAnswerResult? result;
  final int? selectedSingle;
  final List<int> selectedMulti;
  final String blankText;
  final String textAnswer;
  final ValueChanged<int>? onSingle;
  final void Function(int value, bool on)? onMulti;
  final ValueChanged<String>? onBlank;
  final ValueChanged<String>? onText;

  @override
  Widget build(BuildContext context) {
    final correct = result?.isCorrect;
    Color? border;
    if (submitted && correct == true) border = AppColors.greenSoft;
    if (submitted && correct == false) border = Colors.red.shade50;

    Widget input;
    if (question.qtypeCategory == 'choice' && question.options.isNotEmpty) {
      if (question.qtype == 'multi_choice') {
        input = Column(
          children: [
            for (final o in question.options)
              CheckboxListTile(
                dense: true,
                title: Text(o.label),
                value: selectedMulti.contains(o.value),
                onChanged: onMulti == null ? null : (v) => onMulti!(o.value, v == true),
              ),
          ],
        );
      } else {
        input = Column(
          children: [
            for (final o in question.options)
              RadioListTile<int>(
                dense: true,
                title: Text(o.label),
                value: o.value,
                groupValue: selectedSingle ?? 0,
                onChanged: onSingle == null ? null : (v) {
                  if (v != null) onSingle!(v);
                },
              ),
          ],
        );
      }
    } else if (question.qtypeCategory == 'blank') {
      input = TextField(
        key: ValueKey('bank-blank-${question.id}'),
        decoration: const InputDecoration(hintText: '填写答案…', border: OutlineInputBorder(), isDense: true),
        onChanged: onBlank,
        enabled: onBlank != null,
      );
    } else {
      input = TextField(
        key: ValueKey('bank-text-${question.id}'),
        maxLines: 3,
        decoration: const InputDecoration(hintText: '写下你的回答…', border: OutlineInputBorder()),
        onChanged: onText,
        enabled: onText != null,
      );
    }

    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: border != null ? Border.all(color: border.withValues(alpha: 0.6)) : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${index + 1}. ${question.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            input,
            if (submitted && result != null) ...[
              const SizedBox(height: 8),
              Text(
                correct == null
                    ? '待批改'
                    : (correct ? '回答正确' : '回答不对${result!.correctAnswerText.isNotEmpty ? ' · 参考：${result!.correctAnswerText}' : ''}'),
                style: TextStyle(fontSize: 13, color: correct == true ? AppColors.green : (correct == false ? Colors.red : AppColors.gray)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
