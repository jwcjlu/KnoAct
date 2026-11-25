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
                onChanged: ctl.setText,
                onSubmit: ctl.submit,
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

class _ExpressionInput extends StatelessWidget {
  const _ExpressionInput({
    required this.topic,
    required this.text,
    required this.busy,
    required this.submitError,
    required this.onChanged,
    required this.onSubmit,
  });

  final ExpressionTopic topic;
  final String text;
  final bool busy;
  final String? submitError;
  final ValueChanged<String> onChanged;
  final VoidCallback onSubmit;

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
                topic.title,
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
                onChanged: onChanged,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (submitError == 'failed')
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text(
              '没存上，再点一下试试？',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.gray),
            ),
          ),
        FilledButton(
          onPressed: text.trim().isEmpty || busy ? null : onSubmit,
          child: const Text('讲完了'),
        ),
      ],
    );
  }
}
