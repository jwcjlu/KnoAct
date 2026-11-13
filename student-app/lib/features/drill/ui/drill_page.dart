import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../shell/task_page_app_bar.dart';

class DrillPage extends ConsumerWidget {
  const DrillPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: TaskPageAppBar(title: '专项训练'),
      body: const Center(child: Text('会话：引导 → 四步 → 复盘（待接入 content）')),
    );
  }
}
