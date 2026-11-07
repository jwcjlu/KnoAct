import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../data/read_ask_cards_models.dart';
import '../immersive_quiz_controller.dart';

/// Web `.quiz-card`（沉浸阅读对话区内的测验）
class ImmersiveQuizCard extends ConsumerWidget {
  const ImmersiveQuizCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(immersiveQuizProvider);
    final ctl = ref.read(immersiveQuizProvider.notifier);
    if (!s.active) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.line),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (var qi = 0; qi < s.questions.length; qi++)
                _QuizQuestionBlock(
                  index: qi,
                  question: s.questions[qi],
                  chosen: s.answers[s.questions[qi].id],
                  submitted: s.submitted,
                  result: s.submitted ? _resultFor(s, qi) : null,
                  onPick: (i) => ctl.pickAnswer(s.questions[qi].id, i),
                ),
              const SizedBox(height: 8),
              if (s.submitted)
                Text(
                  '答对 ${s.results.where((r) => r.isCorrect).length}/${s.questions.length}',
                  style: const TextStyle(fontSize: 13, color: AppColors.gray),
                )
              else
                FilledButton(
                  onPressed: s.busy || s.answers.length < s.questions.length ? null : ctl.submit,
                  child: s.busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('提交答案'),
                ),
            ],
          ),
        ),
      ),
    );
  }

  ReaderQuizGradeRow? _resultFor(ImmersiveQuizState s, int qi) {
    final q = s.questions[qi];
    for (final r in s.results) {
      if (r.questionId == q.id) return r;
    }
    return qi < s.results.length ? s.results[qi] : null;
  }
}

class _QuizQuestionBlock extends StatelessWidget {
  const _QuizQuestionBlock({
    required this.index,
    required this.question,
    required this.chosen,
    required this.submitted,
    required this.result,
    required this.onPick,
  });

  final int index;
  final ReaderQuizQuestion question;
  final int? chosen;
  final bool submitted;
  final ReaderQuizGradeRow? result;
  final ValueChanged<int> onPick;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(question.prompt, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, height: 1.45)),
          for (var i = 0; i < question.choices.length; i++)
            _ChoiceTile(
              label: '${String.fromCharCode(65 + i)}. ${question.choices[i]}',
              state: _choiceVisual(i, chosen, submitted, result, question.choices.length),
              onTap: submitted ? null : () => onPick(i),
            ),
        ],
      ),
    );
  }

  _ChoiceVisual _choiceVisual(int i, int? chosen, bool submitted, ReaderQuizGradeRow? r, int nChoices) {
    if (!submitted) {
      return chosen == i ? _ChoiceVisual.selected : _ChoiceVisual.normal;
    }
    final ci = r?.correctIndex;
    final sel = r?.selectedIndex ?? chosen;
    final hasKey = ci != null && ci >= 0 && ci < nChoices;
    if (hasKey && i == ci) return _ChoiceVisual.correct;
    if (hasKey && i == sel && sel != ci) return _ChoiceVisual.wrong;
    if (!hasKey && r != null && r.isCorrect && i == sel) return _ChoiceVisual.correct;
    if (!hasKey && r != null && !r.isCorrect && i == sel) return _ChoiceVisual.wrong;
    return _ChoiceVisual.normal;
  }
}

enum _ChoiceVisual { normal, selected, correct, wrong }

class _ChoiceTile extends StatelessWidget {
  const _ChoiceTile({required this.label, required this.state, this.onTap});

  final String label;
  final _ChoiceVisual state;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    Color border = const Color(0xFFE3E6E2);
    Color bg = Colors.white;
    Color fg = const Color(0xFF2B332E);
    String suffix = '';
    switch (state) {
      case _ChoiceVisual.selected:
        border = AppColors.blue;
        bg = AppColors.blueSoft;
        fg = AppColors.blue;
      case _ChoiceVisual.correct:
        border = AppColors.green;
        bg = const Color(0xFFE8F5E9);
        fg = AppColors.green;
        suffix = ' ✓';
      case _ChoiceVisual.wrong:
        border = const Color(0xFFC05B4A);
        bg = const Color(0xFFFDF0EE);
        fg = const Color(0xFFC05B4A);
        suffix = ' ✗';
      case _ChoiceVisual.normal:
        break;
    }
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: border),
            ),
            child: Text('$label$suffix', style: TextStyle(fontSize: 13, color: fg)),
          ),
        ),
      ),
    );
  }
}

/// Web 主动提问卡片
class ImmersiveDiagnosticCard extends ConsumerWidget {
  const ImmersiveDiagnosticCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(immersiveDiagnosticProvider);
    final ctl = ref.read(immersiveDiagnosticProvider.notifier);
    if (!s.active) return const SizedBox.shrink();

    final allAnswered = s.questions.every((q) => (s.replies[q.id] ?? '').trim().isNotEmpty);

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.line),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (s.intro.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(s.intro, style: const TextStyle(fontSize: 13, color: AppColors.gray, height: 1.5)),
                ),
              for (final q in s.questions) ...[
                Text(q.prompt, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, height: 1.45)),
                const SizedBox(height: 4),
                if (q.options.isNotEmpty)
                  for (final o in q.options)
                    _ChoiceTile(
                      label: o.label,
                      state: s.replies[q.id] == o.label ? _ChoiceVisual.selected : _ChoiceVisual.normal,
                      onTap: () => ctl.pickReply(q.id, o.label),
                    )
                else
                  TextField(
                    decoration: const InputDecoration(
                      hintText: '你的回答…',
                      isDense: true,
                      border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
                    ),
                    onChanged: (v) => ctl.pickReply(q.id, v),
                  ),
                const SizedBox(height: 10),
              ],
              FilledButton(
                onPressed: !allAnswered || s.busy ? null : ctl.submit,
                child: s.busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('继续'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
