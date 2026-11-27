import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_page_app_bar.dart';
import '../data/kp_srs_repository.dart';
import '../kp_srs_controller.dart';

/// 知识点复习（遗忘曲线）会话。
/// 文案原则：只说「按计划复习了几个」，不对孩子宣称「已掌握」。
class KpSrsPage extends ConsumerStatefulWidget {
  const KpSrsPage({super.key});

  @override
  ConsumerState<KpSrsPage> createState() => _KpSrsPageState();
}

class _KpSrsPageState extends ConsumerState<KpSrsPage> {
  @override
  void initState() {
    super.initState();
    // 未经入口 init 直接进入（深链/刷新）：按独立入口拉取到期项
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (!ref.read(kpSrsControllerProvider).started) {
        ref.read(kpSrsControllerProvider.notifier).init(taskId: null);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(kpSrsControllerProvider);
    final ctl = ref.read(kpSrsControllerProvider.notifier);
    return Scaffold(
      appBar: TaskPageAppBar(title: s.title.isEmpty ? '知识点复习' : s.title),
      body: _body(s, ctl),
    );
  }

  Widget _body(KpSrsState s, KpSrsController ctl) {
    if (!s.started || s.loading) return const Center(child: CircularProgressIndicator());
    if (s.items.isEmpty && s.error != null) {
      return ErrorCard(message: s.error!, onRetry: ctl.retry);
    }
    if (s.isEmpty) {
      return const Center(
        child: Text('今天没有要复习的知识点', key: ValueKey('kp-srs-empty'), style: TextStyle(color: AppColors.gray)),
      );
    }
    if (s.isDone) return _DonePage(count: s.completed);
    final item = s.current;
    if (item == null) return const SizedBox.shrink();
    return ListView(padding: const EdgeInsets.all(20), children: [
      Text('第 ${s.index + 1} / ${s.items.length} 个',
          key: const ValueKey('kp-srs-progress'), style: const TextStyle(color: AppColors.gray, fontSize: 13)),
      const SizedBox(height: 12),
      _ItemCard(item: item, state: s, ctl: ctl),
      if (s.error != null) ...[
        const SizedBox(height: 12),
        Text(s.error!, key: const ValueKey('kp-srs-error'), style: const TextStyle(color: Colors.red)),
      ],
    ]);
  }
}

class _ItemCard extends StatelessWidget {
  const _ItemCard({required this.item, required this.state, required this.ctl});

  final KpSrsItem item;
  final KpSrsState state;
  final KpSrsController ctl;

  @override
  Widget build(BuildContext context) {
    final fb = state.feedback;
    final hasQuestion = item.prompt.hasQuestion;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (item.lessonTitle.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(color: AppColors.greenSoft, borderRadius: BorderRadius.circular(6)),
            child: Text(item.lessonTitle,
                style: const TextStyle(fontSize: 12, color: AppColors.green, fontWeight: FontWeight.w600)),
          ),
        Text(
          hasQuestion ? item.prompt.question! : item.title,
          key: const ValueKey('kp-srs-prompt'),
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
        ),
        const SizedBox(height: 12),
        if (fb == null)
          hasQuestion ? _answerBox() : _selfRateButtons()
        else
          _feedback(fb),
        if (state.revealContent) ...[
          const SizedBox(height: 12),
          Container(
            key: const ValueKey('kp-srs-content'),
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppColors.orangeSoft, borderRadius: BorderRadius.circular(8)),
            child: Text(item.content, style: const TextStyle(height: 1.5)),
          ),
        ],
        if (fb != null) ...[
          const SizedBox(height: 12),
          FilledButton(
            key: const ValueKey('kp-srs-next'),
            onPressed: ctl.next,
            child: Text(state.index + 1 >= state.items.length ? '完成' : '继续'),
          ),
        ],
      ]),
    );
  }

  Widget _selfRateButtons() {
    final busy = state.busy;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('还记得这个知识点吗？', style: TextStyle(color: AppColors.gray, fontSize: 13)),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
          child: FilledButton(
            key: const ValueKey('kp-srs-remember'),
            onPressed: busy ? null : () => ctl.selfRate(kpResultRemember),
            child: const Text('记得'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton(
            key: const ValueKey('kp-srs-fuzzy'),
            onPressed: busy ? null : () => ctl.selfRate(kpResultFuzzy),
            child: const Text('有点忘'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton(
            key: const ValueKey('kp-srs-forgot'),
            onPressed: busy ? null : () => ctl.selfRate(kpResultForgot),
            child: const Text('忘了'),
          ),
        ),
      ]),
    ]);
  }

  Widget _answerBox() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      TextField(
        // 每题独立 key：切到下一项时输入框自动清空
        key: ValueKey('kp-srs-answer-${state.index}'),
        decoration: const InputDecoration(hintText: '写下你的回答…', isDense: true, border: OutlineInputBorder()),
        minLines: 1,
        maxLines: 4,
        onChanged: ctl.setAnswer,
      ),
      const SizedBox(height: 12),
      FilledButton(
        key: const ValueKey('kp-srs-submit'),
        onPressed: state.busy || state.answer.trim().isEmpty ? null : ctl.submitAnswer,
        child: Text(state.busy ? '正在提交…' : '提交答案'),
      ),
    ]);
  }

  Widget _feedback(KpSrsFeedback fb) {
    final String text;
    final Color color;
    if (fb.graded) {
      text = fb.isCorrect == true ? '答对了' : '这次没答上来，对照下面的内容再看一眼';
      color = fb.isCorrect == true ? AppColors.green : Colors.red;
    } else {
      text = '没关系，再看一眼，之后还会再见到它';
      color = AppColors.gray;
    }
    return Text(text, key: const ValueKey('kp-srs-feedback'), style: TextStyle(color: color, fontWeight: FontWeight.w600));
  }
}

class _DonePage extends StatelessWidget {
  const _DonePage({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(20), children: [
      SectionCard(
        child: Column(children: [
          const Icon(Icons.check_circle, size: 40, color: AppColors.green),
          const SizedBox(height: 8),
          Text('今天按计划复习了 $count 个知识点',
              key: const ValueKey('kp-srs-done'), style: const TextStyle(fontWeight: FontWeight.w700)),
        ]),
      ),
    ]);
  }
}
