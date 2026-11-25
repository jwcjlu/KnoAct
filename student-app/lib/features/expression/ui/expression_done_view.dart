import 'package:flutter/material.dart';

import '../../../core/theme.dart';

/// 写完后的结束页。
///
/// 刻意不评价：本功能不做判定（见 spec 的「五轮失败记录」）。
/// 说「讲得好」等于撒谎——系统并不知道他讲得对不对。
class ExpressionDoneView extends StatelessWidget {
  const ExpressionDoneView({super.key, this.onAgain, this.onBack});

  final VoidCallback? onAgain;
  final VoidCallback? onBack;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.check_circle_outline,
              size: 48,
              color: AppColors.green,
            ),
            const SizedBox(height: 16),
            const Text(
              '记下来了',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text(
              '你讲的这段话，爸爸/妈妈能看到。',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppColors.gray,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton(onPressed: onAgain, child: const Text('再讲一个')),
                const SizedBox(width: 12),
                FilledButton(onPressed: onBack, child: const Text('返回')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
