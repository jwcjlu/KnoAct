import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import '../data/brain_game_models.dart';

/// 毫秒 → "mm:ss"（超过 99 分钟按分钟显示）。
String formatGameMs(int ms) {
  final totalSeconds = ms ~/ 1000;
  final m = (totalSeconds ~/ 60).toString().padLeft(2, '0');
  final s = (totalSeconds % 60).toString().padLeft(2, '0');
  return '$m:$s';
}

/// 三个游戏共用的顶栏：返回、标题、难度分段、计时器、历史最佳。
class GameTopBar extends StatelessWidget {
  const GameTopBar({
    super.key,
    required this.title,
    required this.difficulty,
    required this.onDifficultyChanged,
    required this.elapsedMs,
    required this.bestMs,
    this.onRestart,
  });

  final String title;
  final BrainGameDifficulty difficulty;
  final ValueChanged<BrainGameDifficulty> onDifficultyChanged;
  final int elapsedMs;
  final int? bestMs;
  final VoidCallback? onRestart;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            IconButton(
              onPressed: () => Navigator.of(context).maybePop(),
              icon: const Icon(Icons.arrow_back),
              tooltip: '返回',
            ),
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.blue.withValues(alpha: .10),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                formatGameMs(elapsedMs),
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  fontFeatures: [FontFeature.tabularFigures()],
                ),
              ),
            ),
            if (onRestart != null)
              IconButton(
                onPressed: onRestart,
                icon: const Icon(Icons.refresh),
                tooltip: '重新开始',
              ),
          ],
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            Expanded(
              child: SegmentedButton<BrainGameDifficulty>(
                segments: [
                  for (final d in BrainGameDifficulty.values)
                    ButtonSegment(value: d, label: Text(d.label)),
                ],
                selected: {difficulty},
                showSelectedIcon: false,
                onSelectionChanged: (s) => onDifficultyChanged(s.first),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              bestMs == null ? '最佳 —' : '最佳 ${formatGameMs(bestMs!)}',
              style: const TextStyle(fontSize: 12, color: AppColors.gray),
            ),
          ],
        ),
      ],
    );
  }
}

/// 结束弹层（通关/失败共用）。
Future<void> showGameResultDialog(
  BuildContext context, {
  required String title,
  required String detail,
  required bool showNewRecord,
  required VoidCallback onRestart,
}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(detail, textAlign: TextAlign.center),
          if (showNewRecord) ...[
            const SizedBox(height: 8),
            const Text(
              '新纪录！',
              style: TextStyle(
                color: AppColors.orange,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () {
            Navigator.of(ctx).pop();
            Navigator.of(context).maybePop();
          },
          child: const Text('返回'),
        ),
        FilledButton(
          onPressed: () {
            Navigator.of(ctx).pop();
            onRestart();
          },
          child: const Text('再来一局'),
        ),
      ],
    ),
  );
}
