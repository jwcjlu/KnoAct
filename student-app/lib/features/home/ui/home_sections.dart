import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../data/home_models.dart';
import '../home_logic.dart';

class GreetingHeader extends StatelessWidget {
  const GreetingHeader({super.key, required this.name, required this.points, required this.now});

  final String name;
  final int points;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(dateLabel(now), style: const TextStyle(color: AppColors.gray)),
          const SizedBox(height: 4),
          Text('${greeting(now.hour)}，$name', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
        ]),
      ),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20), border: Border.all(color: AppColors.line)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.star, color: AppColors.gold, size: 18),
          const SizedBox(width: 4),
          Text('$points', style: const TextStyle(fontWeight: FontWeight.w700)),
          const Text(' 积分', style: TextStyle(fontSize: 12, color: AppColors.gray)),
        ]),
      ),
    ]);
  }
}

class PlanCard extends StatelessWidget {
  const PlanCard({super.key, required this.subject, required this.progress, required this.poem, required this.onStart});

  final String subject;
  final LessonProgress progress;
  final Poem poem;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: AppColors.blue,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('今日个性化学习计划', style: TextStyle(color: Colors.white70)),
          const SizedBox(height: 8),
          Text('第 ${progress.current} 课重点学习与旧课复习',
              style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text('根据今日$subject进度和遗忘曲线，AI 安排了新课巩固与到期复习。', style: const TextStyle(color: Colors.white)),
          const SizedBox(height: 12),
          FilledButton.tonal(onPressed: onStart, child: const Text('开始今日学习')),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.92), borderRadius: BorderRadius.circular(14)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('今日勉励 · ${poem.title}', style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(poem.text, style: const TextStyle(height: 1.6)),
              Align(alignment: Alignment.centerRight, child: Text('—— ${poem.author}', style: const TextStyle(color: AppColors.gray))),
            ]),
          ),
        ]),
      ),
    );
  }
}

class TodayProgressCard extends StatelessWidget {
  const TodayProgressCard({super.key, required this.tasks, required this.lesson});

  final List<StudyTask> tasks;
  final LessonProgress lesson;

  static const _subjectColors = {'语文': AppColors.blue, '英语': AppColors.orange, '数学': AppColors.green};

  @override
  Widget build(BuildContext context) {
    final p = dayProgress(tasks);
    final remain = p.total - p.done;
    final perSubject = subjectProgress(tasks);
    final masteredPct = lesson.total > 0 ? lesson.mastered / lesson.total : 0.0;
    return SectionCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(child: Text('今日进度', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          Text('${p.percent}%', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.blue)),
        ]),
        const SizedBox(height: 6),
        Text('${p.done} / ${p.total} 项'),
        Text(
          remain > 0 ? '还差 $remain 项，今日学习就完成啦' : (p.total > 0 ? '全部完成，今天真棒！' : '今天还没有任务'),
          style: const TextStyle(color: AppColors.gray),
        ),
        const SizedBox(height: 8),
        LinearProgressIndicator(value: p.total == 0 ? 0 : p.done / p.total),
        const SizedBox(height: 12),
        for (final s in subjects) ...[
          Row(children: [
            Expanded(child: Text(s)),
            Text('${perSubject[s]!.done}/${perSubject[s]!.total}', style: const TextStyle(color: AppColors.gray)),
          ]),
          LinearProgressIndicator(
            value: perSubject[s]!.total == 0 ? 0 : perSubject[s]!.done / perSubject[s]!.total,
            color: _subjectColors[s],
          ),
          const SizedBox(height: 8),
        ],
        const Divider(),
        const Text('课程进度', style: TextStyle(fontWeight: FontWeight.w600)),
        Text(
          lesson.total > 0 ? '已学到第 ${lesson.current} 课 · ${lesson.mastered} / ${lesson.total} 课' : '请在家长端导入教材后开始学习',
          style: const TextStyle(color: AppColors.gray),
        ),
        const SizedBox(height: 6),
        LinearProgressIndicator(value: masteredPct),
      ]),
    );
  }
}

class SubjectTabs extends StatelessWidget {
  const SubjectTabs({super.key, required this.tasks, required this.current, required this.onSelect});

  final List<StudyTask> tasks;
  final String current;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Wrap(spacing: 8, children: [
      for (final s in subjects)
        ChoiceChip(
          key: ValueKey('subject-$s'),
          selected: s == current,
          onSelected: (_) => onSelect(s),
          label: Text(remainingCount(tasks, s) > 0 ? '$s ${remainingCount(tasks, s)}' : '$s ✓'),
        ),
    ]);
  }
}

class TaskCard extends StatelessWidget {
  const TaskCard({super.key, required this.task, required this.onAction});

  final StudyTask task;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final meta = taskMeta(task.taskType);
    final action = taskAction(task);
    final label = switch (action) {
      TaskAction.done => '已完成',
      TaskAction.waiting => '等待家长确认',
      _ => '开始练习',
    };
    final enabled = action != TaskAction.done && action != TaskAction.waiting;
    return Opacity(
      opacity: isDone(task) ? 0.6 : 1,
      child: SectionCard(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            CircleAvatar(backgroundColor: meta.color.withValues(alpha: 0.12), child: Icon(meta.icon, color: meta.color)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(meta.tag, style: TextStyle(fontSize: 12, color: meta.color, fontWeight: FontWeight.w600)),
                Text(task.title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                if (task.detail.isNotEmpty) Text(task.detail, style: const TextStyle(color: AppColors.gray)),
              ]),
            ),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            if (meta.minutes.isNotEmpty) Text(meta.minutes, style: const TextStyle(color: AppColors.gray, fontSize: 12)),
            const Spacer(),
            Text('+${task.points}', style: const TextStyle(color: AppColors.gold, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              key: ValueKey('task-action-${task.id}'),
              onPressed: enabled ? onAction : null,
              child: Text(label),
            ),
          ),
        ]),
      ),
    );
  }
}

class RedeemCard extends StatelessWidget {
  const RedeemCard({super.key, required this.points, required this.onRedeem});

  final int points;
  final void Function(String device, int minutes) onRedeem;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('积分兑换 · 劳逸结合，快乐成长', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text('当前 $points 积分', style: const TextStyle(color: AppColors.gray)),
        const SizedBox(height: 12),
        Wrap(spacing: 12, runSpacing: 12, children: [
          OutlinedButton.icon(
            key: const ValueKey('redeem-tablet'),
            onPressed: () => onRedeem('tablet', 30),
            icon: const Icon(Icons.tablet_mac),
            label: const Text('平板 30 分钟 · 300 积分'),
          ),
          OutlinedButton.icon(
            key: const ValueKey('redeem-phone'),
            onPressed: () => onRedeem('phone', 20),
            icon: const Icon(Icons.phone_android),
            label: const Text('手机 20 分钟 · 200 积分'),
          ),
        ]),
      ]),
    );
  }
}

class WeeklyPlaceholderCard extends StatelessWidget {
  const WeeklyPlaceholderCard({super.key});

  @override
  Widget build(BuildContext context) => const SectionCard(
        child: Row(children: [
          Expanded(child: Text('本周学习', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          Text('暂无记录', style: TextStyle(color: AppColors.gray)),
        ]),
      );
}
