import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/widgets.dart';
import '../../auth/session.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final child = ref.watch(sessionProvider).value;
    return ListView(padding: const EdgeInsets.all(20), children: [
      SectionCard(
        child: Row(children: [
          CircleAvatar(radius: 26, child: Text(child == null ? '' : child.name.characters.last)),
          const SizedBox(width: 16),
          Expanded(child: Text(child?.name ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700))),
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
