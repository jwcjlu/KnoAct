import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../auth/session.dart';
import '../../brain_games/data/brain_game_models.dart';
import '../../center/center_controller.dart';
import '../../dictation/dictation_controller.dart';
import '../../drill/drill_controller.dart';
import '../../knowledge_review/knowledge_controller.dart';
import '../../kp_srs/kp_srs_controller.dart';
import '../../math_exercise/math_controller.dart';
import '../../reader/reader_controller.dart';
import '../data/home_models.dart';
import '../home_controller.dart';
import '../../shell/task_nav.dart';
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

  Future<void> _onTask(StudyTask t) async {
    switch (taskAction(t)) {
      case TaskAction.openReading:
        await ref.read(readerControllerProvider.notifier).enterCatalog();
        if (!context.mounted) return;
        context.push(taskRoute('/reader', returnTo: '/home'));
      case TaskAction.openListening:
        ref.read(centerControllerProvider.notifier).openForTask(t.id);
        context.go('/center');
      case TaskAction.openMath:
        ref
            .read(mathControllerProvider.notifier)
            .init(
              taskId: t.id,
              title: t.title,
              content: t.content,
            ); // content 作 material 失败兜底
        context.push(taskRoute('/math', returnTo: '/home'));
      case TaskAction.openKnowledge:
        ref
            .read(knowledgeControllerProvider.notifier)
            .init(taskId: t.id, title: t.title, content: t.content);
        context.push(taskRoute('/knowledge', returnTo: '/home'));
      case TaskAction.openDictation:
        ref
            .read(dictationControllerProvider.notifier)
            .init(
              taskId: t.id,
              title: t.title,
              subject: t.subject,
              content: t.content,
            );
        context.push(taskRoute('/dictation', returnTo: '/home'));
      case TaskAction.openBankPractice:
        var bankId = 0;
        var ids = <int>[];
        var extraBankIds = <int>[];
        try {
          final m = jsonDecode(t.content);
          if (m is Map) {
            bankId = (m['bank_id'] as num?)?.toInt() ?? 0;
            final raw = m['question_ids'];
            if (raw is List) {
              ids = raw.map((e) => (e as num).toInt()).toList();
            }
            // 多卷合并任务：除主卷外还可能有别的卷，取题时要一起带上
            final banksRaw = m['banks'];
            if (banksRaw is List) {
              for (final b in banksRaw) {
                if (b is Map) {
                  final bid = (b['bank_id'] as num?)?.toInt() ?? 0;
                  if (bid > 0 && bid != bankId) extraBankIds.add(bid);
                }
              }
            }
          }
        } catch (_) {}
        if (bankId <= 0) {
          showMessage(context, '题库任务配置有误，请联系家长');
          break;
        }
        // 注意：path 与 query 必须分开传。若把 "?a=1&b=2" 整串塞进 path，
        // Uri(path: ...) 会把 ? 转义成 %3F，路由就匹配不上、点了没反应。
        final query = <String, String>{
          'bank_id': '$bankId',
          if (ids.isNotEmpty) 'ids': ids.join(','),
          if (extraBankIds.isNotEmpty)
            'extra_bank_ids': extraBankIds.join(','),
          'task_id': '${t.id}',
        };
        context.push(taskRoute('/bank-exercise',
            returnTo: '/home', query: query));
      case TaskAction.openDrill:
        ref
            .read(drillControllerProvider.notifier)
            .init(taskId: t.id, title: t.title, content: t.content);
        context.push(taskRoute('/drill', returnTo: '/home'));
      case TaskAction.openKpSrs:
        ref
            .read(kpSrsControllerProvider.notifier)
            .init(taskId: t.id, content: t.content, title: t.title);
        context.push(taskRoute('/kp-srs', returnTo: '/home'));
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
      final msg = await ref
          .read(homeControllerProvider.notifier)
          .redeem(device, minutes);
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
      final ownData =
          v != null && v.childId == ref.read(currentChildIdProvider);
      if (next.hasError && ownData && !next.isLoading)
        showMessage(context, '刷新失败，请稍后重试');
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
    return LayoutBuilder(
      builder: (context, c) {
        final wide = c.maxWidth >= 840;
        final columns = c.maxWidth >= 1100 ? 3 : (c.maxWidth >= 600 ? 2 : 1);
        Widget grid(List<StudyTask> list) => _TaskGrid(
          columns: columns,
          children: [
            for (final t in list) TaskCard(task: t, onAction: () => _onTask(t)),
          ],
        );
        final plan = PlanCard(
          subject: data.subject,
          progress: data.snapshot.lessonProgress,
          poem: todayPoem(now),
          onStart: () {
            final ctx = _tasksKey.currentContext;
            if (ctx != null)
              Scrollable.ensureVisible(
                ctx,
                duration: const Duration(milliseconds: 300),
              );
          },
        );
        final progress = TodayProgressCard(
          tasks: data.tasks,
          lesson: data.snapshot.lessonProgress,
        );
        return RefreshIndicator(
          onRefresh: () => ref.read(homeControllerProvider.notifier).reload(),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              GreetingHeader(
                name: data.snapshot.userName,
                points: data.points,
                now: now,
              ),
              const SizedBox(height: 16),
              const _BucketSelector(),
              const SizedBox(height: 16),
              // 个性化学习入口
              Card(
                color: AppColors.blue,
                child: ListTile(
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 8,
                  ),
                  leading: const Icon(
                    Icons.auto_stories,
                    color: Colors.white,
                    size: 32,
                  ),
                  title: const Text(
                    '个性化学习',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                  subtitle: const Text(
                    '选教材读原文，划词查释义、记笔记',
                    style: TextStyle(color: Colors.white70),
                  ),
                  trailing: const Icon(
                    Icons.chevron_right,
                    color: Colors.white,
                  ),
                  onTap: () async {
                    await ref
                        .read(readerControllerProvider.notifier)
                        .enterCatalog();
                    if (!context.mounted) return;
                    context.push(taskRoute('/reader', returnTo: '/home'));
                  },
                ),
              ),
              const SizedBox(height: 16),
              // 磨耳朵入口
              Card(
                color: AppColors.green,
                child: ListTile(
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 8,
                  ),
                  leading: const Icon(
                    Icons.headphones,
                    color: Colors.white,
                    size: 32,
                  ),
                  title: const Text(
                    '磨耳朵',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                  subtitle: const Text(
                    '听课文真人音频，跟读练习',
                    style: TextStyle(color: Colors.white70),
                  ),
                  trailing: const Icon(
                    Icons.chevron_right,
                    color: Colors.white,
                  ),
                  onTap: () =>
                      context.push(taskRoute('/listening', returnTo: '/home')),
                ),
              ),
              const SizedBox(height: 16),
              // 表达练习：独立入口，不进每日任务
              Card(
                child: ListTile(
                  key: const ValueKey('expression-home-entry'),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 8,
                  ),
                  leading: const Icon(
                    Icons.record_voice_over,
                    color: AppColors.blue,
                    size: 32,
                  ),
                  title: const Text(
                    '讲一遍',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                  subtitle: const Text('用自己的话讲讲你学的知识点'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/expression'),
                ),
              ),
              const SizedBox(height: 16),
              // 自然拼读：独立入口，只跟听，不进每日任务、不记掌握度
              Card(
                child: ListTile(
                  key: const ValueKey('phonics-home-entry'),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 8,
                  ),
                  leading: const Icon(
                    Icons.abc,
                    color: AppColors.orange,
                    size: 32,
                  ),
                  title: const Text(
                    '自然拼读',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                  subtitle: const Text('按路径听字母与字母组合怎么读'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/phonics'),
                ),
              ),
              const SizedBox(height: 16),
              // 思维训练：独立入口，孩子自由玩，不进每日任务
              Card(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '思维训练 · 动动脑',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        '数独 · 舒尔特方格 · 数字扫雷',
                        style: TextStyle(fontSize: 12, color: AppColors.gray),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          _BrainGameEntry(
                            icon: Icons.grid_on,
                            label: '数独',
                            route: GameKindRoute.pathOf(BrainGameKind.sudoku),
                          ),
                          const SizedBox(width: 10),
                          _BrainGameEntry(
                            icon: Icons.apps,
                            label: '舒尔特',
                            route: GameKindRoute.pathOf(BrainGameKind.schulte),
                          ),
                          const SizedBox(width: 10),
                          _BrainGameEntry(
                            icon: Icons.flag,
                            label: '扫雷',
                            route: GameKindRoute.pathOf(
                              BrainGameKind.minesweeper,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              if (wide)
                IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(flex: 3, child: plan),
                      const SizedBox(width: 16),
                      Expanded(flex: 2, child: progress),
                    ],
                  ),
                )
              else ...[
                plan,
                const SizedBox(height: 16),
                progress,
              ],
              const SizedBox(height: 24),
              Row(
                key: _tasksKey,
                children: [
                  const Expanded(
                    child: Text(
                      '今日学习任务',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  // 知识点复习：独立入口，现场拉取到期项（不依赖每日任务）
                  OutlinedButton.icon(
                    key: const ValueKey('kp-srs-home-entry'),
                    onPressed: () {
                      ref
                          .read(kpSrsControllerProvider.notifier)
                          .init(taskId: null);
                      context.push(taskRoute('/kp-srs', returnTo: '/home'));
                    },
                    icon: const Icon(Icons.psychology, size: 18),
                    label: const Text('知识点复习'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              SubjectTabs(
                tasks: data.tasks,
                current: data.subject,
                onSelect: (s) =>
                    ref.read(homeControllerProvider.notifier).setSubject(s),
              ),
              const SizedBox(height: 12),
              if (groups.todo.isEmpty && groups.done.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: Text('今天还没有任务，先去学习中心看看吧')),
                )
              else ...[
                Text(
                  '待完成 ${groups.todo.length}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                if (groups.todo.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('本学科任务都完成啦，去别的学科看看吧 🎉'),
                  )
                else
                  grid(groups.todo),
                if (groups.done.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Text(
                    '已完成 ${groups.done.length}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  grid(groups.done),
                ],
              ],
              const SizedBox(height: 24),
              const WeeklyPlaceholderCard(),
              const SizedBox(height: 16),
              RedeemCard(points: data.points, onRedeem: _redeem),
            ],
          ),
        );
      },
    );
  }
}

class _TaskGrid extends StatelessWidget {
  const _TaskGrid({required this.columns, required this.children});

  final int columns;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        const gap = 12.0;
        final width = (c.maxWidth - gap * (columns - 1)) / columns;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: [
            for (final w in children) SizedBox(width: width, child: w),
          ],
        );
      },
    );
  }
}

/// 首页积分学年切换：只有一个桶时隐藏，选中历史学年时显示提示
class _BucketSelector extends ConsumerWidget {
  const _BucketSelector();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(homeBucketsProvider);
    final ctl = ref.read(homeBucketsProvider.notifier);
    if (s.buckets.length <= 1) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          children: [
            for (final b in s.buckets)
              ChoiceChip(
                key: ValueKey('home-bucket-${b.id}'),
                selected: s.bucketId == b.id,
                onSelected: (_) => ctl.setBucket(b.id),
                label: Text(
                  '${b.schoolYear} · ${b.grade}年级${b.isActive ? '（当前）' : ''}',
                ),
              ),
          ],
        ),
        if (s.isReadOnly) ...[
          const SizedBox(height: 8),
          Container(
            key: const ValueKey('home-bucket-readonly-banner'),
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.orangeSoft,
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text(
              '历史学年积分',
              style: TextStyle(
                color: AppColors.orange,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _BrainGameEntry extends StatelessWidget {
  const _BrainGameEntry({
    required this.icon,
    required this.label,
    required this.route,
  });

  final IconData icon;
  final String label;
  final String route;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push(route),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: AppColors.blue.withValues(alpha: .08),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              Icon(icon, size: 22, color: AppColors.blue),
              const SizedBox(height: 6),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
