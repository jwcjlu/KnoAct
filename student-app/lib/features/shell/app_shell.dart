import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../center/center_controller.dart';
import '../home/home_controller.dart';

const _destinations = [
  (icon: Icons.home_outlined, selected: Icons.home, label: '首页'),
  (icon: Icons.menu_book_outlined, selected: Icons.menu_book, label: '学习中心'),
  (icon: Icons.person_outline, selected: Icons.person, label: '我的'),
];

/// 宽度 >= 840 用左侧 NavigationRail，否则底部 NavigationBar
const double kWideBreakpoint = 840;

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int? _lastIndex;

  void _go(int index) =>
      widget.navigationShell.goBranch(index, initialLocation: index == widget.navigationShell.currentIndex);

  void _onIndexChanged(int? from, int to) {
    if (from == 1 && to != 1) ref.read(centerControllerProvider.notifier).leave();
    if (to == 1) ref.read(centerControllerProvider.notifier).enter();
    if (from == null) return;
    if (to == 0) ref.read(homeControllerProvider.notifier).reload();
    if (to == 2) ref.invalidate(pointsProvider);
  }

  @override
  Widget build(BuildContext context) {
    final index = widget.navigationShell.currentIndex;
    if (_lastIndex != index) {
      final from = _lastIndex;
      _lastIndex = index;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _onIndexChanged(from, index);
      });
    }
    return LayoutBuilder(builder: (context, c) {
      if (c.maxWidth >= kWideBreakpoint) {
        return Scaffold(
          body: SafeArea(
            child: Row(children: [
              NavigationRail(
                selectedIndex: index,
                onDestinationSelected: _go,
                labelType: NavigationRailLabelType.all,
                leading: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text('知学伴', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.blue)),
                ),
                destinations: [
                  for (final d in _destinations)
                    NavigationRailDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selected), label: Text(d.label)),
                ],
              ),
              const VerticalDivider(width: 1),
              Expanded(
                child: Align(
                  alignment: Alignment.topCenter,
                  child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1200), child: widget.navigationShell),
                ),
              ),
            ]),
          ),
        );
      }
      return Scaffold(
        body: SafeArea(child: widget.navigationShell),
        bottomNavigationBar: NavigationBar(
          selectedIndex: index,
          onDestinationSelected: _go,
          destinations: [
            for (final d in _destinations)
              NavigationDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selected), label: d.label),
          ],
        ),
      );
    });
  }
}
