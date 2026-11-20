import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/sudoku.dart';
import 'brain_game_shell.dart';
import 'brain_game_theme.dart';

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
      final p = generateSudoku(_difficulty.id, random: math.Random());
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

  Color? _cellColor(int r, int c) {
    if (r == _wrongRow && c == _wrongCol) return BrainPalette.sudokuWrong;
    if (r == _selectedRow && c == _selectedCol) {
      return BrainPalette.sudokuSelected;
    }
    final p = _puzzle;
    if (_selectedRow != null && _selectedCol != null && p != null) {
      final spec = p.spec;
      final sameBox =
          r ~/ spec.boxRows == _selectedRow! ~/ spec.boxRows &&
          c ~/ spec.boxCols == _selectedCol! ~/ spec.boxCols;
      if (r == _selectedRow || c == _selectedCol || sameBox) {
        return BrainPalette.sudokuPeer;
      }
    }
    return null;
  }

  /// 棋盘：细线分出每一格，粗线分出宫，两者都清晰可见。
  Widget _buildBoard(SudokuSpec spec) {
    final p = _puzzle!;
    final n = spec.size;

    return AspectRatio(
      aspectRatio: 1,
      child: Container(
        key: const ValueKey('sudoku-grid'),
        decoration: BoxDecoration(color: BrainPalette.sudokuBg),
        child: LayoutBuilder(
          builder: (context, c) {
            final cellW = c.maxWidth / n;
            final cellH = c.maxHeight / n;
            return Stack(
              children: [
                // 高亮底（选中 / 同行列宫 / 落错）
                for (var r = 0; r < n; r++)
                  for (var c2 = 0; c2 < n; c2++)
                    if (_cellColor(r, c2) != null)
                      Positioned(
                        left: c2 * cellW,
                        top: r * cellH,
                        width: cellW,
                        height: cellH,
                        child: ColoredBox(color: _cellColor(r, c2)!),
                      ),
                // 所有格线：细线每格、粗线分宫
                Positioned.fill(
                  child: CustomPaint(
                    painter: _SudokuGridPainter(
                      size: n,
                      boxRows: spec.boxRows,
                      boxCols: spec.boxCols,
                      thin: BrainPalette.sudokuLine,
                      thick: BrainPalette.sudokuBoxLine,
                    ),
                  ),
                ),
                // 选中格描边（压在格线之上，仍可见）
                if (_selectedRow != null && _selectedCol != null)
                  Positioned(
                    left: _selectedCol! * cellW,
                    top: _selectedRow! * cellH,
                    width: cellW,
                    height: cellH,
                    child: IgnorePointer(
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: BrainPalette.sudokuInput,
                            width: 2.5,
                          ),
                        ),
                      ),
                    ),
                  ),
                // 数字 + 点击区
                for (var r = 0; r < n; r++)
                  for (var c2 = 0; c2 < n; c2++)
                    Positioned(
                      left: c2 * cellW,
                      top: r * cellH,
                      width: cellW,
                      height: cellH,
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTap: () => _select(r, c2),
                        child: Center(
                          child: FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Padding(
                              padding: const EdgeInsets.all(2),
                              child: Text(
                                _cells[r][c2] == 0 ? '' : '${_cells[r][c2]}',
                                style: TextStyle(
                                  fontSize: n >= 9 ? 22 : 28,
                                  height: 1.1,
                                  fontWeight: p.isGiven(r, c2)
                                      ? FontWeight.w700
                                      : FontWeight.w500,
                                  color: p.isGiven(r, c2)
                                      ? BrainPalette.sudokuGiven
                                      : BrainPalette.sudokuInput,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
              ],
            );
          },
        ),
      ),
    );
  }

  /// 数字条：固定高度、按盘面大小自适应宽度，永不换行。
  Widget _pad(SudokuSpec spec) {
    return LayoutBuilder(
      builder: (context, c) {
        final n = spec.size;
        const gap = 6.0;
        final w = (c.maxWidth - gap * (n - 1)) / n;
        final side = math.min(w, 46.0);
        return Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var v = 1; v <= n; v++) ...[
              if (v > 1) const SizedBox(width: gap),
              SizedBox(
                width: side,
                height: side,
                child: Material(
                  color: BrainPalette.sudokuPadBg,
                  borderRadius: BorderRadius.circular(10),
                  child: InkWell(
                    key: ValueKey('sudoku-pad-$v'),
                    borderRadius: BorderRadius.circular(10),
                    onTap: () => _place(v),
                    child: Center(
                      child: Text(
                        '$v',
                        style: TextStyle(
                          fontSize: side * .45,
                          fontWeight: FontWeight.w700,
                          color: BrainPalette.sudokuInput,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = _puzzle;
    final best = _stats[_kind]?[_difficulty]?.bestMs;

    return Scaffold(
      backgroundColor: Colors.white,
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
            accent: BrainPalette.sudokuInput,
          ),
        ),
      ),
      body: p == null
          ? GameGenerateError(onRetry: _restart, detail: _generateError)
          : SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                child: Column(
                  children: [
                    // 棋盘吃掉所有剩余高度（一屏内不滚动），并保持正方形
                    Expanded(child: FitSquare(child: _buildBoard(p.spec))),
                    const SizedBox(height: 12),
                    _pad(p.spec),
                    const SizedBox(height: 8),
                    const Text(
                      '点格子后在下方选数字；填错会标红并清空',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 11, color: AppColors.gray),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}

/// 数独棋盘线：每格细线 + 每宫粗线，避免「看不出有格」。
class _SudokuGridPainter extends CustomPainter {
  _SudokuGridPainter({
    required this.size,
    required this.boxRows,
    required this.boxCols,
    required this.thin,
    required this.thick,
  });

  final int size;
  final int boxRows;
  final int boxCols;
  final Color thin;
  final Color thick;

  @override
  void paint(Canvas canvas, Size s) {
    final cellW = s.width / size;
    final cellH = s.height / size;

    final thinPaint = Paint()
      ..color = thin
      ..strokeWidth = 1.5
      ..isAntiAlias = true;
    final thickPaint = Paint()
      ..color = thick
      ..strokeWidth = 2.5
      ..isAntiAlias = true;

    // 细线：跳过会成为宫线的位置，避免叠色发虚
    for (var i = 1; i < size; i++) {
      final x = i * cellW;
      final y = i * cellH;
      if (i % boxCols != 0) {
        canvas.drawLine(Offset(x, 0), Offset(x, s.height), thinPaint);
      }
      if (i % boxRows != 0) {
        canvas.drawLine(Offset(0, y), Offset(s.width, y), thinPaint);
      }
    }

    // 粗线：宫边界
    for (var i = 0; i < size; i++) {
      final x = i * cellW;
      final y = i * cellH;
      if (i % boxCols == 0) {
        canvas.drawLine(Offset(x, 0), Offset(x, s.height), thickPaint);
      }
      if (i % boxRows == 0) {
        canvas.drawLine(Offset(0, y), Offset(s.width, y), thickPaint);
      }
    }

    // 最外框
    canvas.drawRect(
      Rect.fromLTWH(0, 0, s.width, s.height),
      Paint()
        ..color = thick
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5,
    );
  }

  @override
  bool shouldRepaint(_SudokuGridPainter old) =>
      old.size != size ||
      old.boxRows != boxRows ||
      old.boxCols != boxCols ||
      old.thin != thin ||
      old.thick != thick;
}
