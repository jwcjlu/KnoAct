import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/sudoku.dart';
import 'brain_game_shell.dart';

/// 落错格的标红底色（`AppColors` 无 red，用局部常量）
const _gameWrong = Color(0x1FC05B4A);

class SudokuPage extends ConsumerStatefulWidget {
  const SudokuPage({super.key});

  @override
  ConsumerState<SudokuPage> createState() => _SudokuPageState();
}

class _SudokuPageState extends ConsumerState<SudokuPage> {
  static const _kind = BrainGameKind.sudoku;

  BrainGameDifficulty _difficulty = BrainGameDifficulty.easy;
  BrainGameStats _stats = const {};

  /// 当前题面（null = 生成失败或未就绪）。字段名勿与 build 用方法重名。
  SudokuPuzzle? _puzzle;
  List<List<int>> _cells = const [];
  String? _generateError;
  int? _selectedRow;
  int? _selectedCol;
  int? _wrongRow;
  int? _wrongCol;

  final _sw = Stopwatch();
  Timer? _ticker;
  bool _finished = false;
  int _moves = 0;
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

  /// 生成题面；异常时进入错误态，由 UI 提供「重新生成」。
  void _newGame() {
    try {
      final p = generateSudoku(_difficulty.id, random: Random());
      _puzzle = p;
      _cells = [for (final row in p.givens) List<int>.from(row)];
      _generateError = null;
      _selectedRow = null;
      _selectedCol = null;
      _wrongRow = null;
      _wrongCol = null;
      _moves = 0;
      _finished = false;
      _elapsedMs = 0;
      _sw
        ..reset()
        ..start();
    } catch (e) {
      // 生成异常不白屏：显示「重新生成」按钮（规格容错节要求）
      _puzzle = null;
      _cells = const [];
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

  void _select(int r, int c) {
    final p = _puzzle;
    if (p == null || _finished || p.isGiven(r, c)) return;
    setState(() {
      _selectedRow = r;
      _selectedCol = c;
    });
  }

  Future<void> _place(int value) async {
    final p = _puzzle;
    final r = _selectedRow;
    final c = _selectedCol;
    if (p == null || r == null || c == null || _finished) return;

    if (value == p.solution[r][c]) {
      setState(() {
        _cells[r][c] = value;
        _moves++;
        _wrongRow = null;
        _wrongCol = null;
      });
      if (p.isSolved(_cells)) await _finish();
    } else {
      // 落错：标红后自动清空该格，避免「填满但未通关且无提示」的静默态
      setState(() {
        _cells[r][c] = 0;
        _moves++;
        _wrongRow = r;
        _wrongCol = c;
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
      } catch (_) {
        // 提交失败静默忽略，不影响本次游玩
      }
    }
    if (!mounted) return;
    await _loadStats();
    if (!mounted) return;
    await showGameResultDialog(
      context,
      title: '完成！',
      detail: '用时 ${formatGameMs(_elapsedMs)} · 落子 $_moves 次',
      // 未成功提交时没有 is_best，不显示新纪录
      showNewRecord: submitted && isBest,
      onRestart: _restart,
    );
  }

  Color _cellColor(int r, int c) {
    if (r == _wrongRow && c == _wrongCol) return _gameWrong;
    if (r == _selectedRow && c == _selectedCol) {
      return AppColors.blue.withValues(alpha: .14);
    }
    final p = _puzzle;
    if (_selectedRow != null && _selectedCol != null && p != null) {
      final spec = p.spec;
      final sameBox =
          r ~/ spec.boxRows == _selectedRow! ~/ spec.boxRows &&
          c ~/ spec.boxCols == _selectedCol! ~/ spec.boxCols;
      // 同行 / 同列 / 同宫都浅蓝底（规格要求）
      if (r == _selectedRow || c == _selectedCol || sameBox) {
        return AppColors.blue.withValues(alpha: .05);
      }
    }
    return Colors.transparent;
  }

  Widget _buildBoard(SudokuSpec spec) {
    final p = _puzzle!;
    final n = spec.size;
    return AspectRatio(
      aspectRatio: 1,
      child: Container(
        key: const ValueKey('sudoku-grid'),
        decoration: BoxDecoration(border: Border.all(color: AppColors.line)),
        child: Column(
          children: [
            for (var r = 0; r < n; r++)
              Expanded(
                child: Row(
                  children: [
                    for (var c = 0; c < n; c++)
                      Expanded(
                        child: GestureDetector(
                          onTap: () => _select(r, c),
                          child: Container(
                            decoration: BoxDecoration(
                              color: _cellColor(r, c),
                              // 选中格加主题蓝描边（规格要求）
                              border: r == _selectedRow && c == _selectedCol
                                  ? Border.all(color: AppColors.blue, width: 2)
                                  : Border(
                                      right: BorderSide(
                                        color:
                                            (c + 1) % spec.boxCols == 0 &&
                                                c != n - 1
                                            ? AppColors.ink
                                            : AppColors.line,
                                        width:
                                            (c + 1) % spec.boxCols == 0 &&
                                                c != n - 1
                                            ? 2
                                            : .5,
                                      ),
                                      bottom: BorderSide(
                                        color:
                                            (r + 1) % spec.boxRows == 0 &&
                                                r != n - 1
                                            ? AppColors.ink
                                            : AppColors.line,
                                        width:
                                            (r + 1) % spec.boxRows == 0 &&
                                                r != n - 1
                                            ? 2
                                            : .5,
                                      ),
                                    ),
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              _cells[r][c] == 0 ? '' : '${_cells[r][c]}',
                              style: TextStyle(
                                fontSize: n >= 9 ? 18 : 22,
                                fontWeight: p.isGiven(r, c)
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                                color: p.isGiven(r, c)
                                    ? AppColors.ink
                                    : AppColors.blue,
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _pad(SudokuSpec spec) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: [
        for (var v = 1; v <= spec.size; v++)
          SizedBox(
            width: 44,
            height: 44,
            child: FilledButton(
              key: ValueKey('sudoku-pad-$v'),
              style: FilledButton.styleFrom(padding: EdgeInsets.zero),
              onPressed: () => _place(v),
              child: Text('$v'),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = _puzzle;
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
      body: p == null
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
                _buildBoard(p.spec),
                const SizedBox(height: 20),
                _pad(p.spec),
                const SizedBox(height: 16),
                const Text(
                  '点格子后在下方选数字；填错会标红并清空',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: AppColors.gray),
                ),
              ],
            ),
    );
  }
}
