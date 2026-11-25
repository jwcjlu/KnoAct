import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_page_app_bar.dart';
import '../data/expression_repository.dart';
import '../expression_controller.dart';
import 'expression_done_view.dart';

class ExpressionPage extends ConsumerWidget {
  const ExpressionPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _LoadTopicsOnce(
      child: Consumer(
        builder: (context, ref, _) {
          final s = ref.watch(expressionControllerProvider);
          final ctl = ref.read(expressionControllerProvider.notifier);

          if (s.done) {
            return Scaffold(
              appBar: const TaskPageAppBar(title: '讲一遍'),
              body: ExpressionDoneView(
                onAgain: ctl.again,
                onBack: () => Navigator.of(context).maybePop(),
              ),
            );
          }

          return Scaffold(
            appBar: const TaskPageAppBar(title: '讲一遍'),
            body: switch (s.error) {
              'forbidden' => const _MessageView(
                message: '这个功能要三年级以上才能用，再长大一点吧。',
              ),
              'failed' => _FailedView(onRetry: ctl.loadTopics),
              _ when s.selected == null => _TopicPicker(
                topics: s.topics,
                onSelect: ctl.select,
              ),
              _ => _ExpressionInput(
                topic: s.selected!,
                text: s.text,
                busy: s.busy,
                submitError: s.submitError,
                probeOpen: s.probeOpen,
                probeQuestion: s.probeQuestion,
                probeError: s.probeError,
                probeBusy: s.probeBusy,
                onChanged: ctl.setText,
                onSubmit: ctl.submit,
                onOpenProbe: ctl.openProbe,
                onAnswerProbe: ctl.answerProbe,
              ),
            },
          );
        },
      ),
    );
  }
}

class _LoadTopicsOnce extends ConsumerStatefulWidget {
  const _LoadTopicsOnce({required this.child});

  final Widget child;

  @override
  ConsumerState<_LoadTopicsOnce> createState() => _LoadTopicsOnceState();
}

class _LoadTopicsOnceState extends ConsumerState<_LoadTopicsOnce> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        ref.read(expressionControllerProvider.notifier).loadTopics();
      }
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

class _MessageView extends StatelessWidget {
  const _MessageView({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(color: AppColors.gray),
        ),
      ),
    );
  }
}

class _FailedView extends StatelessWidget {
  const _FailedView({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              '没加载出来，待会儿再试试？',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.gray),
            ),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('重试')),
          ],
        ),
      ),
    );
  }
}

class _TopicPicker extends StatelessWidget {
  const _TopicPicker({required this.topics, required this.onSelect});

  final List<ExpressionTopic> topics;
  final ValueChanged<ExpressionTopic> onSelect;

  @override
  Widget build(BuildContext context) {
    if (topics.isEmpty) {
      return const _MessageView(message: '还没有可以讲的知识点，先去学一课吧。');
    }
    return ListView.separated(
      padding: const EdgeInsets.all(20),
      itemCount: topics.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final topic = topics[index];
        return SectionCard(
          padding: EdgeInsets.zero,
          child: ListTile(
            title: Text(
              topic.title,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            trailing: const Icon(Icons.chevron_right, color: AppColors.gray),
            onTap: () => onSelect(topic),
          ),
        );
      },
    );
  }
}

class _ExpressionInput extends StatefulWidget {
  const _ExpressionInput({
    required this.topic,
    required this.text,
    required this.busy,
    required this.submitError,
    required this.probeOpen,
    required this.probeQuestion,
    required this.probeError,
    required this.probeBusy,
    required this.onChanged,
    required this.onSubmit,
    required this.onOpenProbe,
    required this.onAnswerProbe,
  });

  final ExpressionTopic topic;
  final String text;
  final bool busy;
  final String? submitError;
  final bool probeOpen;
  final String probeQuestion;
  final String? probeError;
  final bool probeBusy;
  final ValueChanged<String> onChanged;
  final VoidCallback onSubmit;
  final VoidCallback onOpenProbe;
  final ValueChanged<String> onAnswerProbe;

  @override
  State<_ExpressionInput> createState() => _ExpressionInputState();
}

class _ExpressionInputState extends State<_ExpressionInput> {
  final _probeAnswerController = TextEditingController();

  @override
  void didUpdateWidget(covariant _ExpressionInput oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.probeQuestion != widget.probeQuestion &&
        widget.probeQuestion.isNotEmpty) {
      _probeAnswerController.clear();
    }
  }

  @override
  void dispose() {
    _probeAnswerController.dispose();
    super.dispose();
  }

  bool get _hasBody => widget.text.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.topic.title,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                '用你自己的话讲讲这个知识点，就当讲给一个完全不懂的人听。',
                style: TextStyle(color: AppColors.gray, height: 1.6),
              ),
              const SizedBox(height: 16),
              TextField(
                key: const ValueKey('expression-input'),
                maxLines: 8,
                maxLength: 5000,
                decoration: const InputDecoration(
                  hintText: '随便说，说多少都行…',
                  border: OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
                onChanged: widget.onChanged,
              ),
            ],
          ),
        ),
        if (_hasBody && !widget.probeOpen) ...[
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              key: const ValueKey('expression-probe-open'),
              onPressed: widget.probeBusy ? null : widget.onOpenProbe,
              child: const Text('让 AI 问问我'),
            ),
          ),
        ],
        if (widget.probeOpen) ...[
          const SizedBox(height: 8),
          SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.probeBusy)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Center(
                      child: SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  ),
                if (widget.probeError != null)
                  const Text(
                    '这会儿问不了',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.gray),
                  ),
                if (widget.probeQuestion.isNotEmpty) ...[
                  Text(
                    widget.probeQuestion,
                    style: const TextStyle(
                      color: AppColors.ink,
                      height: 1.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const ValueKey('expression-probe-answer'),
                    maxLines: 3,
                    maxLength: 2000,
                    controller: _probeAnswerController,
                    decoration: const InputDecoration(
                      hintText: '写下你的回答…',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.tonal(
                    onPressed: widget.probeBusy ||
                            widget.probeQuestion.isEmpty ||
                            _probeAnswerController.text.trim().isEmpty
                        ? null
                        : () => widget.onAnswerProbe(
                              _probeAnswerController.text.trim(),
                            ),
                    child: const Text('回答'),
                  ),
                ],
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        if (widget.submitError == 'failed')
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text(
              '没存上，再点一下试试？',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.gray),
            ),
          ),
        FilledButton(
          onPressed: !_hasBody || widget.busy ? null : widget.onSubmit,
          child: const Text('讲完了'),
        ),
      ],
    );
  }
}
