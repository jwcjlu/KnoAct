import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../shell/task_page_app_bar.dart';
import '../drill_controller.dart';
import '../data/drill_repository.dart';
import 'drill_npc.dart';

class DrillPage extends ConsumerWidget {
  const DrillPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(drillControllerProvider);
    final ctl = ref.read(drillControllerProvider.notifier);
    return Scaffold(
      appBar: TaskPageAppBar(title: s.title.isEmpty ? '专项训练' : s.title),
      body: switch (s.phase) {
        DrillPhase.intro => _IntroView(s: s, ctl: ctl),
        DrillPhase.steps => _StepsView(s: s, ctl: ctl),
        DrillPhase.review => _ReviewView(s: s, ctl: ctl),
      },
    );
  }
}

// ── 引导页 ────────────────────────────────────────────────
class _IntroView extends StatelessWidget {
  const _IntroView({required this.s, required this.ctl});
  final DrillState s;
  final DrillController ctl;

  @override
  Widget build(BuildContext context) {
    final session = s.session;
    final intro = session?.intro;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (s.npc != null) ...[
          NpcBubble(message: s.npc!),
          const SizedBox(height: 16),
        ],
        _card(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('🚀 今日任务', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              if (intro != null && intro.situation.isNotEmpty)
                Text(intro.situation, style: const TextStyle(fontSize: 14, height: 1.6)),
              const SizedBox(height: 12),
              if (intro != null && intro.goal.isNotEmpty)
                _goalRow('🎯 目标', intro.goal),
              if (intro != null && intro.route.isNotEmpty)
                _goalRow('🗺️ 路线', intro.route),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (session != null) _RouteCard(steps: session.steps),
        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: () => ctl.startSteps(),
            child: const Text('开始闯关 →'),
          ),
        ),
      ],
    );
  }
}

Widget _goalRow(String label, String text) => Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.blue)),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13, height: 1.5))),
        ],
      ),
    );

class _RouteCard extends StatelessWidget {
  const _RouteCard({required this.steps});
  final List<String> steps;

  static const _labels = {
    'recognize': '发现规律', 'recall': '记住', 'produce': '造句', 'quiz': '快测',
    'structure': '结构卡', 'drill': '练一练', 'apply': '用一用', 'closure': '收尾',
    'observe': '观察', 'classify': '归类', 'formula': '归纳', 'trap': '陷阱验证',
  };

  @override
  Widget build(BuildContext context) {
    return _card(
      Row(
        children: [
          for (var i = 0; i < steps.length; i++) ...[
            if (i > 0)
              const Expanded(
                child: Divider(color: AppColors.line, thickness: 2),
              ),
            Column(
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: i == 0 ? AppColors.blue : AppColors.blueSoft,
                  child: Text('${i + 1}',
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          color: i == 0 ? Colors.white : AppColors.blue)),
                ),
                const SizedBox(height: 4),
                Text(
                  _labels[steps[i]] ?? steps[i],
                  style: const TextStyle(fontSize: 11, color: AppColors.gray),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

// ── 四步 ──────────────────────────────────────────────────
class _StepsView extends StatelessWidget {
  const _StepsView({required this.s, required this.ctl});
  final DrillState s;
  final DrillController ctl;

  @override
  Widget build(BuildContext context) {
    final session = s.session;
    if (session == null) {
      return const Center(child: Text('任务内容加载失败', style: TextStyle(color: AppColors.gray)));
    }
    return Column(
      children: [
        _ProgressBar(steps: session.steps, current: s.stepIndex),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (s.npc != null) ...[
                NpcBubble(message: s.npc!, onTap: () => ctl.revealRuleNow()),
                const SizedBox(height: 16),
              ],
              _StepBody(s: s, ctl: ctl),
            ],
          ),
        ),
      ],
    );
  }
}

class _ProgressBar extends StatelessWidget {
  const _ProgressBar({required this.steps, required this.current});
  final List<String> steps;
  final int current;

  static const _labels = {
    'recognize': '认', 'recall': '记', 'produce': '用', 'quiz': '快测',
    'structure': '结构', 'drill': '练', 'apply': '用', 'closure': '收尾',
    'observe': '观察', 'classify': '归类', 'formula': '归纳', 'trap': '陷阱',
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          for (var i = 0; i < steps.length; i++) ...[
            if (i > 0) const Expanded(child: SizedBox()),
            Column(
              children: [
                CircleAvatar(
                  radius: 13,
                  backgroundColor: i < current
                      ? AppColors.green
                      : i == current
                          ? AppColors.blue
                          : const Color(0xFFECEFEA),
                  child: Text('${i + 1}',
                      style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          color: i <= current ? Colors.white : AppColors.gray)),
                ),
                const SizedBox(height: 3),
                Text(
                  _labels[steps[i]] ?? steps[i],
                  style: TextStyle(
                      fontSize: 10.5,
                      color: i == current ? AppColors.blue : AppColors.gray,
                      fontWeight: i == current ? FontWeight.w700 : FontWeight.w400),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _StepBody extends StatefulWidget {
  const _StepBody({required this.s, required this.ctl});
  final DrillState s;
  final DrillController ctl;

  @override
  State<_StepBody> createState() => _StepBodyState();
}

class _StepBodyState extends State<_StepBody> {
  final _answer = TextEditingController();

  @override
  void dispose() {
    _answer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.s;
    final ctl = widget.ctl;
    final session = s.session!;
    final step = session.steps[s.stepIndex];
    final item = session.items.isNotEmpty ? session.items[s.itemIndex.clamp(0, session.items.length - 1)] : null;

    switch (step) {
      case 'recognize':
      case 'structure':
      case 'observe':
        return _RuleCard(session: session, reveal: s.revealRule, ctl: ctl);
      case 'recall':
      case 'drill':
      case 'formula':
      case 'closure':
      case 'classify':
      case 'trap':
        return _itemCard(
          context,
          item,
          title: '第 ${s.itemIndex + 1} 题',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (item != null)
                Text('补全：${item.primary}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              TextField(
                controller: _answer,
                decoration: const InputDecoration(
                  hintText: '写下答案…',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
        );
      case 'produce':
      case 'apply':
        return _itemCard(
          context,
          item,
          title: '造句 · 第 ${s.itemIndex + 1} 题',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (item != null)
                Text('用「${item.primary}」造一个句子',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              TextField(
                controller: _answer,
                maxLines: 2,
                decoration: const InputDecoration(
                  hintText: '写下你的句子…',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
        );
      case 'quiz':
        final quiz = session.quiz;
        if (quiz.isEmpty) {
          return const Center(child: Text('本步无题目', style: TextStyle(color: AppColors.gray)));
        }
        final q = quiz[s.itemIndex.clamp(0, quiz.length - 1)];
        return _itemCard(
          context,
          null,
          title: '快测 · 第 ${s.itemIndex + 1}/${quiz.length} 题',
          badge: q.qtype == 'spot_error' ? '🔍 找茬' : null,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(q.prompt, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              TextField(
                controller: _answer,
                decoration: InputDecoration(
                  hintText: q.qtype == 'spot_error' ? '把正确的写出来…' : '写下答案…',
                  isDense: true,
                  border: const OutlineInputBorder(),
                ),
              ),
            ],
          ),
        );
      default:
        return const Center(child: Text('未知步骤', style: TextStyle(color: AppColors.gray)));
    }
  }

  Widget _itemCard(BuildContext context, DrillItem? item,
      {required String title, String? badge, required Widget child}) {
    return _card(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (badge != null) ...[
                _badge(badge, color: const Color(0xFFD64545), bg: const Color(0xFFFBECEC)),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: Text(title, style: const TextStyle(fontSize: 12, color: AppColors.gray, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          child,
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: widget.s.answered
                ? FilledButton(
                    onPressed: () => widget.ctl.nextItem(),
                    child: const Text('下一步 →'),
                  )
                : FilledButton(
                    onPressed: widget.s.busy ? null : () => _onSubmit(item),
                    child: Text(widget.s.busy ? '正在判分…' : '提交'),
                  ),
          ),
        ],
      ),
    );
  }

  Future<void> _onSubmit(DrillItem? item) {
    final session = widget.s.session!;
    final step = session.steps[widget.s.stepIndex];
    final answer = _answer.text.trim();
    if (answer.isEmpty) return Future.value();
    if (step == 'produce' || step == 'apply') {
      return widget.ctl.submitSentence(itemId: item?.id ?? 0, sentence: answer);
    }
    return widget.ctl.submitStep(itemId: item?.id ?? 0, answer: answer, requestHint: false);
  }
}

class _RuleCard extends StatelessWidget {
  const _RuleCard({required this.session, required this.reveal, required this.ctl});
  final DrillSession session;
  final bool reveal;
  final DrillController ctl;

  @override
  Widget build(BuildContext context) {
    final rule = session.groupRule;
    return _card(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🔍 先观察，自己发现',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: AppColors.blue)),
          const SizedBox(height: 10),
          for (final e in rule.examples)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(e.oe, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                  Text(e.oc, style: const TextStyle(fontSize: 12, color: AppColors.gray)),
                ],
              ),
            ),
          if (rule.question.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 8),
              child: Text('🤔 ${rule.question}',
                  style: const TextStyle(fontSize: 13, height: 1.6, color: Color(0xFF6B4A12))),
            ),
          if (reveal && rule.reveal.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.greenSoft,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text('✨ ${rule.reveal}',
                  style: const TextStyle(fontSize: 13, height: 1.6, color: AppColors.green)),
            ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: reveal
                ? FilledButton(
                    onPressed: () => ctl.nextItem(),
                    child: const Text('下一步 →'),
                  )
                : OutlinedButton(
                    onPressed: () => ctl.revealRuleNow(),
                    child: const Text('揭晓规律'),
                  ),
          ),
        ],
      ),
    );
  }
}

// ── 复盘 ──────────────────────────────────────────────────
class _ReviewView extends StatelessWidget {
  const _ReviewView({required this.s, required this.ctl});
  final DrillState s;
  final DrillController ctl;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (s.npc != null) ...[
          NpcBubble(message: s.npc!),
          const SizedBox(height: 16),
        ],
        _card(
          Column(
            children: [
              const Text('🏆', style: TextStyle(fontSize: 52)),
              const SizedBox(height: 8),
              const Text('闯关完成！', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var i = 0; i < 3; i++)
                    Icon(
                      i < s.stars ? Icons.star : Icons.star_border,
                      color: i < s.stars ? AppColors.gold : AppColors.line,
                      size: 34,
                    ),
                ],
              ),
              const SizedBox(height: 12),
              const Text('需加强的内容会进入间隔复习，过几天再见，多见面次就牢啦',
                  style: TextStyle(fontSize: 12, color: AppColors.gray, height: 1.5)),
            ],
          ),
        ),
      ],
    );
  }
}

// ── 通用 ──────────────────────────────────────────────────
Widget _card(Widget child) => Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.line),
      ),
      child: child,
    );

Widget _badge(String text, {required Color color, required Color bg}) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: color)),
    );
