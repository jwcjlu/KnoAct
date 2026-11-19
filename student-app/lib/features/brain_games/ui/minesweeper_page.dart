import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/minesweeper.dart';
import 'brain_game_shell.dart';

/// 扫雷红色标记 / 棋盘底色（`AppColors` 无 red / card）
const _gameRed = Color(0xFFC05B4A);
const _gameCellClosed = Color(0xFFDCE1DA);

class MinesweeperPage extends ConsumerStatefulWidget {
  const MinesweeperPage({super.key});

  @override
  ConsumerState<MinesweeperPage> createState() => _MinesweeperPageState();
}

class _MinesweeperPageState extends ConsumerState<MinesweeperPage> {
  static const _kind = BrainGameKind.minesweeper;

  BrainGameDifficulty _difficulty = BrainGameDifficulty.easy;
  BrainGameStats _stats = const {};

  /// 首点前为 null（不布雷）。
  MinesweeperBoard? _board;
  MinesweeperSpec _spec = minesweeperSpecFor('easy');
  final _opened = <int>{};
  final _flags = <int>{};
  int _moves = 0;
  bool _boom = false;

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

  /// 重置一局（首点前不布雷，因此这里是同步的、不会抛）。
  void _newGame() {
    _spec = minesweeperSpecFor(_difficulty.id);
    _board = null;
    _opened.clear();
    _flags.clear();
    _moves = 0;
    _boom = false;
    _finished = false;
    _elapsedMs = 0;
    _sw
      ..reset()
      ..stop();
  }

  void _restart() => setState(_newGame);

  void _changeDifficulty(BrainGameDifficulty d) {
    if (d == _difficulty) return;
    setState(() {
      _difficulty = d;
      _newGame();
    });
  }

  Future<void> _tap(int index) async {
    if (_finished) return;
    if (_flags.contains(index)) return;

    var board = _board;
    if (board == null) {
      // 首点：先布雷，保证该格不是雷
      board = generateMinesweeper(
        _difficulty.id,
        safeIndex: index,
        random: Random(),
      );
      _board = board;
      _sw.start();
    }

    if (board.isMine(index)) {
      _moves++;
      setState(() => _boom = true);
      await _finish(solved: false);
      return;
    }

    final newly = board.reveal(index);
    _moves++;
    setState(() => _opened.addAll(newly));

    if (board.isCleared(_opened)) {
      await _finish(solved: true);
    }
  }

  void _toggleFlag(int index) {
    if (_finished || _opened.contains(index)) return;
    setState(() {
      if (!_flags.remove(index)) _flags.add(index);
    });
  }

  Future<void> _finish({required bool solved}) async {
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
              solved: solved,
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
      title: solved ? '通关！' : '踩到雷了',
      detail: '用时 ${formatGameMs(_elapsedMs)} · 点开 $_moves 次',
      // 失败局永不显示新纪录
      showNewRecord: solved && submitted && isBest,
      onRestart: _restart,
    );
  }

  static const _numberColors = <int, Color>{
    1: Color(0xFF3158E8),
    2: Color(0xFF2E8B57),
    3: Color(0xFFC05B4A),
    4: Color(0xFF6B4FA8),
    5: Color(0xFFAA5A23),
    6: Color(0xFF1F7A8C),
    7: Color(0xFF444444),
    8: Color(0xFF8E9691),
  };

  Widget _cell(int index) {
    final board = _board;
    final r = index ~/ _spec.cols;
    final c = index % _spec.cols;

    // 统一外包 AspectRatio：已开格若只有 Container 会按内容收缩，导致整盘行高不一致
    return AspectRatio(aspectRatio: 1, child: _cellBody(index, board, r, c));
  }

  Widget _cellBody(int index, MinesweeperBoard? board, int r, int c) {
    if (board == null) {
      // 首点前统一灰色凸起
      return _greyCell(index);
    }

    if (_boom && board.isMine(index)) {
      return Container(
        decoration: BoxDecoration(
          color: _gameRed.withValues(alpha: .18),
          border: Border.all(color: AppColors.line),
        ),
        alignment: Alignment.center,
        child: Icon(Icons.dangerous, size: 16, color: _gameRed),
      );
    }

    if (!_opened.contains(index)) {
      return _greyCell(index, flag: _flags.contains(index));
    }

    final adj = board.adjacentAt(r, c);
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.line),
      ),
      alignment: Alignment.center,
      child: adj > 0
          ? Text(
              '$adj',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 14,
                color: _numberColors[adj] ?? AppColors.ink,
              ),
            )
          : const SizedBox.shrink(),
    );
  }

  Widget _greyCell(int index, {bool flag = false}) {
    return GestureDetector(
      key: ValueKey('mine-cell-$index'),
      onTap: () => _tap(index),
      onLongPress: () => _toggleFlag(index),
      child: Container(
        decoration: BoxDecoration(
          color: _gameCellClosed,
          border: Border.all(color: AppColors.line),
          borderRadius: BorderRadius.circular(3),
        ),
        alignment: Alignment.center,
        child: flag
            ? Icon(Icons.flag, size: 14, color: _gameRed)
            : const SizedBox.shrink(),
      ),
    );
  }

  Widget _boardWidget() {
    return Column(
      children: [
        for (var r = 0; r < _spec.rows; r++)
          Row(
            children: [
              for (var c = 0; c < _spec.cols; c++)
                Expanded(child: _cell(r * _spec.cols + c)),
            ],
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    final remaining = _spec.mines - _flags.length;
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
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Text(
                _board == null ? '点一格开始' : '剩余 $remaining 雷',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              const Text(
                '长按插旗',
                style: TextStyle(color: AppColors.gray, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            key: const ValueKey('minesweeper-board'),
            child: _boardWidget(),
          ),
          const SizedBox(height: 16),
          const Text(
            '数字表示周围 8 格的地雷数',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: AppColors.gray),
          ),
        ],
      ),
    );
  }
}
