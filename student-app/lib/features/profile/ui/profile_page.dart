import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../auth/session.dart';
import '../../home/home_controller.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final child = ref.watch(sessionProvider).value;
    final points = ref.watch(pointsProvider);
    return ListView(padding: const EdgeInsets.all(20), children: [
      SectionCard(
        child: Row(children: [
          CircleAvatar(radius: 26, child: Text(child == null ? '' : child.name.characters.last)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(child?.name ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              Text(
                points.when(data: (p) => '$p 积分', loading: () => '积分加载中…', error: (_, _) => '积分加载失败'),
                style: const TextStyle(color: AppColors.gray),
              ),
            ]),
          ),
        ]),
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () => ref.read(sessionProvider.notifier).logout(),
        icon: const Icon(Icons.logout),
        label: const Text('退出登录'),
      ),
    ]);
  }
}
