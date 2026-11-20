import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/schulte.dart';
import 'brain_game_shell.dart';
import 'brain_game_theme.dart';

class SchultePage extends ConsumerStatefulWidget {
  const SchultePage({super.key});

  @override
  ConsumerState<SchultePage> createState() => _SchultePageState();
}

class _SchultePageState extends ConsumerState<SchultePage> {
  static const _kind = BrainGameKind.schulte;

  BrainGameDifficulty _difficulty = BrainGameDifficulty.easy;
  BrainGameStats _stats = const {};
  SchulteBoard? _board;
  String? _generateError;
  final _cleared = <int>{};
  int _next = 1;
  int _errors = 0;
  int _moves = 0;
  int _shake = 0;

  /// 最近一次点错的数字，用于给它加红色边框。
  int? _wrongValue;

  final _sw = Stopwatch();
  Timer? _ticker;
  bool _finished = false;
  int _elapsedMs = 0;

  @override
  void initState() {
    super.initState();
    _newGame();
    _loadStats();
    _ticker = Timer.periodic(const Duration(milliseconds: 100), (_) {
      if (!mounted || _finished) return;
      setState(() => _elapsedMs = _sw.elapsedMilliseconds);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  int? get _userId => ref.read(currentChildIdProvider);

  Future<void> _loadStats() async {
    final uid = _userId;
    if (uid == null) return;
    final s = await ref.read(brainGameRepositoryProvider).stats(userId: uid);
    if (!mounted) return;
    setState(() => _stats = s);
  }

  /// 生成题面；异常时进入错误态（不白屏）。
  void _newGame() {
    try {
      final b = generateSchulte(_difficulty.id, random: Random());
      _board = b;
      _generateError = null;
      _cleared.clear();
      _next = 1;
      _errors = 0;
      _moves = 0;
      _shake = 0;
      _wrongValue = null;
      _finished = false;
      _elapsedMs = 0;
      _sw
        ..reset()
        ..start();
    } catch (e) {
      _board = null;
      _generateError = '$e';
      _finished = true;
      _sw.stop();
    }
  }

  void _restart() => setState(_newGame);

  void _changeDifficulty(BrainGameDifficulty d) {
    if (d == _difficulty) return;
    setState(() {
      _difficulty = d;
      _newGame();
    });
  }

  Future<void> _tap(int value) async {
    final b = _board;
    if (b == null || _finished || _cleared.contains(value)) return;
    if (value == _next) {
      setState(() {
        _moves++;
        _cleared.add(value);
        _next++;
        _wrongValue = null;
      });
      if (b.isComplete(_cleared)) await _finish();
    } else {
      setState(() {
        _moves++;
        _errors++;
        _wrongValue = value;
        _shake++;
      });
    }
  }

  Future<void> _finish() async {
    _sw.stop();
    setState(() {
      _finished = true;
      _elapsedMs = _sw.elapsedMilliseconds;
    });
    final uid = _userId;
    var isBest = false;
    var submitted = false;
    if (uid != null) {
      try {
        final r = await ref
            .read(brainGameRepositoryProvider)
            .postResult(
              userId: uid,
              kind: _kind,
              difficulty: _difficulty,
              durationMs: _elapsedMs,
              moves: _moves,
              solved: true,
            );
        submitted = true;
        isBest = r.isBest;
      } catch (_) {}
    }
    if (!mounted) return;
    await _loadStats();
    if (!mounted) return;
    await showGameResultDialog(
      context,
      title: '完成！',
      detail: '用时 ${formatGameMs(_elapsedMs)} · 错误 $_errors 次',
      showNewRecord: submitted && isBest,
      onRestart: _restart,
    );
  }

  Widget _cell(int value, int size) {
    final cleared = _cleared.contains(value);
    final wrong = _wrongValue == value;

    if (cleared) {
      // 已点掉的格子：留一块很淡的底，不显示数字，保持网格完整
      return DecoratedBox(
        decoration: BoxDecoration(
          color: BrainPalette.schulteCleared,
          borderRadius: BorderRadius.circular(10),
        ),
      );
    }

    return Material(
      key: ValueKey('schulte-cell-$value'),
      color: BrainPalette.schulteTile,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(
          color: wrong
              ? BrainPalette.schulteAccent
              : BrainPalette.schulteTileBorder,
          width: wrong ? 2 : 1,
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () => _tap(value),
        child: Center(
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Padding(
              padding: const EdgeInsets.all(4),
              child: Text(
                '$value',
                style: TextStyle(
                  fontSize: size >= 5 ? 24 : 30,
                  fontWeight: FontWeight.w700,
                  color: wrong
                      ? BrainPalette.schulteAccent
                      : BrainPalette.schulteTileText,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _boardWidget(SchulteBoard b) {
    final size = b.size;
    const gap = 6.0;
    return AspectRatio(
      aspectRatio: 1,
      child: LayoutBuilder(
        builder: (context, c) {
          final side = (c.maxWidth - gap * (size - 1)) / size;
          return Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (var r = 0; r < size; r++) ...[
                if (r > 0) const SizedBox(height: gap),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    for (var c2 = 0; c2 < size; c2++) ...[
                      if (c2 > 0) const SizedBox(width: gap),
                      SizedBox(
                        width: side,
                        height: side,
                        child: _cell(b.numbers[r * size + c2], size),
                      ),
                    ],
                  ],
                ),
              ],
            ],
          );
        },
      ),
    );
  }

  /// 顶部三栏统计：用时 / 下一个 / 错误。
  Widget _statBar(SchulteBoard b) {
    Widget item(String label, String value, {Color? color, Key? key}) =>
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: const TextStyle(fontSize: 11, color: AppColors.gray),
              ),
              const SizedBox(height: 2),
              Text(
                value,
                key: key,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: color ?? BrainPalette.schulteTileText,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
        );

    final done = _cleared.length;
    final pct = b.max == 0 ? 0.0 : done / b.max;
    return Column(
      children: [
        Row(
          children: [
            item(
              '用时',
              formatGameMs(_elapsedMs),
              key: const ValueKey('schulte-time'),
            ),
            item(
              '下一个',
              '$_next',
              key: const ValueKey('schulte-next'),
              color: BrainPalette.schulteAccent,
            ),
            item(
              '错误',
              '$_errors',
              key: const ValueKey('schulte-errors'),
              color: _errors > 0 ? BrainPalette.schulteAccent : null,
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: LinearProgressIndicator(
            value: pct,
            minHeight: 4,
            backgroundColor: BrainPalette.schulteTileBorder,
            valueColor: const AlwaysStoppedAnimation(
              BrainPalette.schulteAccent,
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final b = _board;
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    return Scaffold(
      backgroundColor: BrainPalette.schulteBg,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(80),
        child: SafeArea(
          bottom: false,
          child: GameTopBar(
            title: _kind.label,
            difficulty: _difficulty,
            onDifficultyChanged: _changeDifficulty,
            elapsedMs: _elapsedMs,
            bestMs: best,
            onRestart: _restart,
            accent: BrainPalette.schulteAccent,
          ),
        ),
      ),
      body: b == null
          ? GameGenerateError(onRetry: _restart, detail: _generateError)
          : SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                child: Column(
                  children: [
                    _statBar(b),
                    const SizedBox(height: 12),
                    Expanded(
                      child: TweenAnimationBuilder<double>(
                        key: ValueKey('schulte-shake-$_shake'),
                        tween: Tween(begin: _shake == 0 ? 0 : -7, end: 0),
                        duration: const Duration(milliseconds: 170),
                        curve: Curves.easeOut,
                        builder: (context, dx, child) => Transform.translate(
                          offset: Offset(dx, 0),
                          child: child,
                        ),
                        child: Container(
                          key: const ValueKey('schulte-board'),
                          child: FitSquare(child: _boardWidget(b)),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      '按 1 → N 的顺序依次点击数字',
                      style: TextStyle(fontSize: 11, color: AppColors.gray),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
