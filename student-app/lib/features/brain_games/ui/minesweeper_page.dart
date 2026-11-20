import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/session.dart';
import '../../../core/theme.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/minesweeper.dart';
import 'brain_game_shell.dart';
import 'brain_game_theme.dart';

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
  int? _boomIndex;

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
    _boomIndex = null;
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
      setState(() {
        _boom = true;
        _boomIndex = index;
      });
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

  Widget _cell(int index) {
    final board = _board;
    final r = index ~/ _spec.cols;
    final c = index % _spec.cols;
    return _cellBody(index, board, r, c);
  }

  /// 未开格：立体凸起（左上白、右下深灰）。
  Widget _raisedCell({required Widget child, Color? color, Key? key}) {
    return Container(
      key: key,
      decoration: BoxDecoration(
        color: color ?? BrainPalette.mineClosed,
        border: const Border(
          top: BorderSide(color: BrainPalette.mineBevelLight, width: 2),
          left: BorderSide(color: BrainPalette.mineBevelLight, width: 2),
          bottom: BorderSide(color: BrainPalette.mineBevelDark, width: 2),
          right: BorderSide(color: BrainPalette.mineBevelDark, width: 2),
        ),
      ),
      alignment: Alignment.center,
      child: child,
    );
  }

  /// 已开格：平坦凹陷（右下白、左上深灰 + 细网格线）。
  Widget _sunkenCell({required Widget child, Color? color}) {
    return Container(
      decoration: BoxDecoration(
        color: color ?? BrainPalette.mineOpen,
        border: const Border(
          top: BorderSide(color: BrainPalette.mineGridLine, width: 1),
          left: BorderSide(color: BrainPalette.mineGridLine, width: 1),
          bottom: BorderSide(color: BrainPalette.mineBevelLight, width: 1),
          right: BorderSide(color: BrainPalette.mineBevelLight, width: 1),
        ),
      ),
      alignment: Alignment.center,
      child: child,
    );
  }

  Widget _cellBody(int index, MinesweeperBoard? board, int r, int c) {
    if (board == null) {
      // 首点前统一灰色凸起
      return _greyCell(index);
    }

    // 踩中的那颗雷用红底标出来
    if (_boomIndex == index) {
      return _sunkenCell(
        color: const Color(0xFFE23B2E),
        child: Image.asset(
          'assets/brain_games/mine.png',
          width: 16,
          height: 16,
          filterQuality: FilterQuality.high,
        ),
      );
    }

    if (!_opened.contains(index)) {
      // 失败后把未点开的雷也显示出来
      if (_boom && board.isMine(index)) {
        return _sunkenCell(
          child: Image.asset(
            'assets/brain_games/mine.png',
            width: 16,
            height: 16,
            filterQuality: FilterQuality.high,
          ),
        );
      }
      return _greyCell(index, flag: _flags.contains(index));
    }

    final adj = board.adjacentAt(r, c);
    return _sunkenCell(
      child: adj > 0
          ? FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                '$adj',
                style: TextStyle(
                  fontWeight: FontWeight.w900,
                  fontSize: 15,
                  color: BrainPalette.mineNumber[adj] ?? Colors.black,
                ),
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
      child: _raisedCell(
        child: flag
            ? Image.asset(
                'assets/brain_games/flag.png',
                width: 14,
                height: 14,
                filterQuality: FilterQuality.high,
              )
            : const SizedBox.shrink(),
      ),
    );
  }

  /// 棋盘：等分成 rows × cols，整块缩放到剩余空间内（绝不滚动）。
  Widget _boardWidget() {
    return AspectRatio(
      key: const ValueKey('minesweeper-board'),
      aspectRatio: _spec.cols / _spec.rows,
      child: Container(
        padding: const EdgeInsets.all(3),
        color: BrainPalette.minePanelBg,
        child: Column(
          children: [
            for (var r = 0; r < _spec.rows; r++)
              Expanded(
                child: Row(
                  children: [
                    for (var c = 0; c < _spec.cols; c++)
                      Expanded(child: _cell(r * _spec.cols + c)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// 经典 LCD 数显：黑底 + 红色等宽数字。
  Widget _lcd(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: BrainPalette.mineLcd,
        borderRadius: BorderRadius.circular(2),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: BrainPalette.mineDigits,
          fontSize: 17,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.5,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
    );
  }

  /// 表情：进行中 smile；踩雷 lose；通关 win（来自 zyrate/Minesweeper 图标集）。
  String get _faceAsset {
    if (!_finished) return 'assets/brain_games/smile.png';
    return _boom ? 'assets/brain_games/lose.png' : 'assets/brain_games/win.png';
  }

  @override
  Widget build(BuildContext context) {
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    final remaining = _spec.mines - _flags.length;
    final secs = (_elapsedMs ~/ 1000).clamp(0, 999);

    return Scaffold(
      backgroundColor: BrainPalette.mineBg,
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
            accent: BrainPalette.mineLcd,
          ),
        ),
      ),
      body: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: Column(
            children: [
              const SizedBox(height: 4),
              // 状态栏：剩余雷数 / 表情重开 / 计时
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: BrainPalette.minePanelBg,
                  border: Border.all(color: BrainPalette.mineBevelDark),
                ),
                child: Row(
                  children: [
                    _lcd(remaining.toString().padLeft(3, '0')),
                    const Spacer(),
                    GestureDetector(
                      onTap: _restart,
                      child: _raisedCell(
                        child: Padding(
                          padding: const EdgeInsets.all(3),
                          child: Image.asset(
                            _faceAsset,
                            key: const ValueKey('mine-face'),
                            width: 26,
                            height: 26,
                            filterQuality: FilterQuality.high,
                          ),
                        ),
                      ),
                    ),
                    const Spacer(),
                    _lcd(secs.toString().padLeft(3, '0')),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              Expanded(child: Center(child: _boardWidget())),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    _board == null ? '点一格开始' : '剩余 $remaining 雷',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF3C3C3C),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    '长按插旗',
                    style: TextStyle(fontSize: 11, color: AppColors.gray),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
