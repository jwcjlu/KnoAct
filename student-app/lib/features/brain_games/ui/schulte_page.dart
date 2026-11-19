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

/// 点错抖动用的边框红（`AppColors` 无 red）
const _gameRed = Color(0xFFC05B4A);

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
    _ticker = Timer.periodic(const Duration(milliseconds: 200), (_) {
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
    // 点错时给该格加红色边框（规格要求「点错红色抖动」的可见反馈）
    final wrong = _wrongValue == value;
    return AnimatedOpacity(
      opacity: cleared ? 0 : 1,
      duration: const Duration(milliseconds: 220),
      child: IgnorePointer(
        ignoring: cleared,
        child: AspectRatio(
          aspectRatio: 1,
          child: Padding(
            padding: const EdgeInsets.all(3),
            child: Material(
              color: cleared
                  ? AppColors.green.withValues(alpha: .25)
                  : AppColors.blue.withValues(alpha: .08),
              // 注意：Material 不能同时传 borderRadius 与 shape（框架断言会抛异常）
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: wrong
                    ? const BorderSide(color: _gameRed, width: 2)
                    : BorderSide.none,
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _tap(value),
                child: Center(
                  child: Text(
                    '$value',
                    style: TextStyle(
                      fontSize: size >= 5 ? 22 : 26,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
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
    return Column(
      children: [
        for (var r = 0; r < size; r++)
          Row(
            children: [
              for (var c = 0; c < size; c++)
                Expanded(child: _cell(b.numbers[r * size + c], size)),
            ],
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final b = _board;
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(108),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: GameTopBar(
              title: _kind.label,
              difficulty: _difficulty,
              onDifficultyChanged: _changeDifficulty,
              elapsedMs: _elapsedMs,
              bestMs: best,
              onRestart: _restart,
            ),
          ),
        ),
      ),
      body: b == null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('题面生成失败，请点下方重新生成'),
                    if (_generateError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          _generateError!,
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.gray,
                          ),
                        ),
                      ),
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: _restart,
                      child: const Text('重新生成'),
                    ),
                  ],
                ),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Row(
                  children: [
                    Text(
                      '下一个：$_next',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '错误 $_errors',
                      style: const TextStyle(color: AppColors.gray),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // 点错时左右轻微抖动：key 变化触发一次从 -6px 到 0 的位移
                TweenAnimationBuilder<double>(
                  key: ValueKey('schulte-shake-$_shake'),
                  tween: Tween(begin: _shake == 0 ? 0 : -6, end: 0),
                  duration: const Duration(milliseconds: 160),
                  curve: Curves.easeOut,
                  builder: (context, dx, child) =>
                      Transform.translate(offset: Offset(dx, 0), child: child),
                  child: Container(
                    key: const ValueKey('schulte-board'),
                    child: _boardWidget(b),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  '按 1 → N 的顺序依次点击数字',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: AppColors.gray),
                ),
              ],
            ),
    );
  }
}
