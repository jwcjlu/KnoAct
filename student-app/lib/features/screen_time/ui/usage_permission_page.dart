import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/screen_time_repository.dart';

class UsagePermissionPage extends ConsumerWidget {
  const UsagePermissionPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(usageApiProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('屏幕时间')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('开启「使用情况访问」后，家长才能看到你的设备使用时长。',
                style: TextStyle(fontSize: 16)),
            const SizedBox(height: 12),
            const Text('路径：设置 → 使用情况访问 → 允许「知学伴」。'),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => api.openUsageAccessSettings(),
              child: const Text('去开启'),
            ),
          ],
        ),
      ),
    );
  }
}
