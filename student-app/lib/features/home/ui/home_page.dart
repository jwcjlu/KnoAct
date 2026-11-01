import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets.dart';
import '../../auth/session.dart';
import '../../center/center_controller.dart';
import '../../center/center_logic.dart';
import '../data/home_models.dart';
import '../home_controller.dart';
import '../home_logic.dart';
import 'home_sections.dart';

class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  final _tasksKey = GlobalKey();
  bool _redeeming = false;

  void _onTask(StudyTask t) {
    switch (taskAction(t)) {
      case TaskAction.openReading:
        ref.read(centerControllerProvider.notifier).openForTask(t.id, CenterTab.reading);
        context.go('/center');
      case TaskAction.openListening:
        ref.read(centerControllerProvider.notifier).openForTask(t.id, CenterTab.listening);
        context.go('/center');
      case TaskAction.comingSoon:
        showMessage(context, '该练习即将在 App 上线，可先在网页版完成');
      case TaskAction.done:
      case TaskAction.waiting:
        break;
    }
  }

  Future<void> _redeem(String device, int minutes) async {
    if (_redeeming) return;
    _redeeming = true;
    try {
      final msg = await ref.read(homeControllerProvider.notifier).redeem(device, minutes);
      if (mounted) showMessage(context, msg);
    } catch (_) {
      if (mounted) showMessage(context, '兑换失败，请稍后重试');
    } finally {
      _redeeming = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(homeControllerProvider, (prev, next) {
      final v = next.value;
      final ownData = v != null && v.childId == ref.read(currentChildIdProvider);
      if (next.hasError && ownData && !next.isLoading) showMessage(context, '刷新失败，请稍后重试');
    });
    final uid = ref.watch(currentChildIdProvider);
    final async = ref.watch(homeControllerProvider);
    // 换孩子时 provider 可能还带着上一个孩子的数据，不能显示
    final data = async.value?.childId == uid ? async.value : null;
    if (data == null) {
      if (async.hasError && !async.isLoading) {
        return ErrorCard(
          message: '首页加载失败，请检查网络或后端服务',
          onRetry: () => ref.read(homeControllerProvider.notifier).reload(),
        );
      }
      return const Center(child: CircularProgressIndicator());
    }
    final now = DateTime.now();
    final groups = groupForSubject(data.tasks, data.subject);
    return LayoutBuilder(builder: (context, c) {
      final wide = c.maxWidth >= 840;
      final columns = c.maxWidth >= 1100 ? 3 : (c.maxWidth >= 600 ? 2 : 1);
      Widget grid(List<StudyTask> list) => _TaskGrid(columns: columns, children: [
            for (final t in list) TaskCard(task: t, onAction: () => _onTask(t)),
          ]);
      final plan = PlanCard(
        subject: data.subject,
        progress: data.snapshot.lessonProgress,
        poem: todayPoem(now),
        onStart: () {
          final ctx = _tasksKey.currentContext;
          if (ctx != null) Scrollable.ensureVisible(ctx, duration: const Duration(milliseconds: 300));
        },
      );
      final progress = TodayProgressCard(tasks: data.tasks, lesson: data.snapshot.lessonProgress);
      return RefreshIndicator(
        onRefresh: () => ref.read(homeControllerProvider.notifier).reload(),
        child: ListView(padding: const EdgeInsets.all(20), children: [
          GreetingHeader(name: data.snapshot.userName, points: data.points, now: now),
          const SizedBox(height: 16),
          if (wide)
            IntrinsicHeight(
              child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Expanded(flex: 3, child: plan),
                const SizedBox(width: 16),
                Expanded(flex: 2, child: progress),
              ]),
            )
          else ...[
            plan,
            const SizedBox(height: 16),
            progress,
          ],
          const SizedBox(height: 24),
          Row(key: _tasksKey, children: [
            const Expanded(child: Text('今日学习任务', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700))),
          ]),
          const SizedBox(height: 8),
          SubjectTabs(
            tasks: data.tasks,
            current: data.subject,
            onSelect: (s) => ref.read(homeControllerProvider.notifier).setSubject(s),
          ),
          const SizedBox(height: 12),
          if (groups.todo.isEmpty && groups.done.isEmpty)
            const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('今天还没有任务，先去学习中心看看吧')))
          else ...[
            Text('待完成 ${groups.todo.length}', style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (groups.todo.isEmpty)
              const Padding(padding: EdgeInsets.all(12), child: Text('本学科任务都完成啦，去别的学科看看吧 🎉'))
            else
              grid(groups.todo),
            if (groups.done.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text('已完成 ${groups.done.length}', style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              grid(groups.done),
            ],
          ],
          const SizedBox(height: 24),
          const WeeklyPlaceholderCard(),
          const SizedBox(height: 16),
          RedeemCard(points: data.points, onRedeem: _redeem),
        ]),
      );
    });
  }
}

class _TaskGrid extends StatelessWidget {
  const _TaskGrid({required this.columns, required this.children});

  final int columns;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      const gap = 12.0;
      final width = (c.maxWidth - gap * (columns - 1)) / columns;
      return Wrap(spacing: gap, runSpacing: gap, children: [
        for (final w in children) SizedBox(width: width, child: w),
      ]);
    });
  }
}
