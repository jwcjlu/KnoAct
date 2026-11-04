import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/screen_time_repository.dart';
import 'usage_permission_page.dart';

class ScreenTimePage extends ConsumerWidget {
  const ScreenTimePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(usageApiProvider);
    return FutureBuilder<bool>(
      future: api.hasUsageAccess(),
      builder: (context, snap) {
        final granted = snap.data ?? false;
        if (!granted) return const UsagePermissionPage();
        return Scaffold(
          appBar: AppBar(title: const Text('屏幕时间')),
          body: const Center(child: Text('今天的使用时长将在这里展示')),
        );
      },
    );
  }
}
