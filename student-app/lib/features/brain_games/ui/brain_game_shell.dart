import 'dart:math' as math;

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

/// 把棋盘按「可用空间内最大的正方形」摆放，保证一屏放得下、不需要滚动。
class FitSquare extends StatelessWidget {
  const FitSquare({super.key, required this.child, this.maxSide});

  final Widget child;
  final double? maxSide;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        var side = math.min(c.maxWidth, c.maxHeight);
        if (maxSide != null) side = math.min(side, maxSide!);
        return Center(
          child: SizedBox(width: side, height: side, child: child),
        );
      },
    );
  }
}

/// 紧凑顶栏：返回、标题、计时、重开 + 一行难度胶囊。总高约 76，给棋盘留足空间。
class GameTopBar extends StatelessWidget {
  const GameTopBar({
    super.key,
    required this.title,
    required this.difficulty,
    required this.onDifficultyChanged,
    required this.elapsedMs,
    required this.bestMs,
    this.onRestart,
    this.accent = AppColors.blue,
  });

  final String title;
  final BrainGameDifficulty difficulty;
  final ValueChanged<BrainGameDifficulty> onDifficultyChanged;
  final int elapsedMs;
  final int? bestMs;
  final VoidCallback? onRestart;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 2, 8, 2),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: 40,
            child: Row(
              children: [
                IconButton(
                  onPressed: () => Navigator.of(context).maybePop(),
                  icon: const Icon(Icons.arrow_back, size: 20),
                  tooltip: '返回',
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 36,
                    minHeight: 36,
                  ),
                ),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const Spacer(),
                Text(
                  formatGameMs(elapsedMs),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: accent,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 8),
                if (onRestart != null)
                  IconButton(
                    onPressed: onRestart,
                    icon: const Icon(Icons.refresh, size: 20),
                    tooltip: '重新开始',
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(
                      minWidth: 36,
                      minHeight: 36,
                    ),
                  ),
              ],
            ),
          ),
          SizedBox(
            height: 34,
            child: Row(
              children: [
                Expanded(
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    padding: EdgeInsets.zero,
                    itemCount: BrainGameDifficulty.values.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 6),
                    itemBuilder: (context, i) {
                      final d = BrainGameDifficulty.values[i];
                      final on = d == difficulty;
                      return GestureDetector(
                        onTap: () => onDifficultyChanged(d),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 140),
                          padding: const EdgeInsets.symmetric(horizontal: 14),
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: on ? accent : Colors.transparent,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: on
                                  ? accent
                                  : AppColors.line.withValues(alpha: 1),
                            ),
                          ),
                          child: Text(
                            d.label,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: on ? Colors.white : AppColors.gray,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  bestMs == null ? '最佳 —' : '最佳 ${formatGameMs(bestMs!)}',
                  style: const TextStyle(fontSize: 11, color: AppColors.gray),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 题面生成失败的统一兜底（不白屏，给「重新生成」）。
class GameGenerateError extends StatelessWidget {
  const GameGenerateError({super.key, required this.onRetry, this.detail});

  final VoidCallback onRetry;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('题面生成失败，请重新生成'),
            if (detail != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  detail!,
                  style: const TextStyle(fontSize: 11, color: AppColors.gray),
                ),
              ),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('重新生成')),
          ],
        ),
      ),
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
