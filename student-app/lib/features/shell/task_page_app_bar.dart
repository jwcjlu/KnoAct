import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import 'task_nav.dart';

/// 任务页顶栏内容（放在 [Scaffold.appBar] 或页面 [Column] 首行均可）。
class TaskPageNavRow extends ConsumerWidget {
  const TaskPageNavRow({
    super.key,
    required this.title,
    this.returnTo,
    this.actions = const [],
  });

  final String title;
  final String? returnTo;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rt = returnTo ?? returnToFromState(context);
    return Material(
      color: Colors.white,
      child: Container(
        height: kToolbarHeight,
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AppColors.line)),
        ),
        padding: const EdgeInsets.only(right: 4),
        child: Row(
          children: [
            IconButton(
              tooltip: '返回',
              icon: const Icon(Icons.arrow_back),
              onPressed: () => popOrReturn(context, returnTo: rt),
            ),
            Expanded(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
              ),
            ),
            ...actions,
            TextButton.icon(
              onPressed: () => goHome(ref, context),
              icon: const Icon(Icons.home_rounded, color: AppColors.blue),
              label: const Text('首页', style: TextStyle(color: AppColors.blue, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shell 外任务页统一顶栏：返回（pop / returnTo）+ 右侧首页（D1）。
class TaskPageAppBar extends ConsumerWidget implements PreferredSizeWidget {
  const TaskPageAppBar({
    super.key,
    required this.title,
    this.returnTo,
    this.actions = const [],
  });

  final String title;
  final String? returnTo;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PreferredSize(
      preferredSize: preferredSize,
      child: TaskPageNavRow(title: title, returnTo: returnTo, actions: actions),
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
