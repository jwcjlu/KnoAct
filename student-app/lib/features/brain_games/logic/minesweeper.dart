import 'dart:math';

/// 一档扫雷的规格。
typedef MinesweeperSpec = ({int rows, int cols, int mines});

MinesweeperSpec minesweeperSpecFor(String difficultyId) =>
    switch (difficultyId) {
      'medium' => (rows: 9, cols: 9, mines: 12),
      'hard' => (rows: 12, cols: 12, mines: 24),
      _ => (rows: 6, cols: 6, mines: 5),
    };

class MinesweeperBoard {
  MinesweeperBoard({
    required this.rows,
    required this.cols,
    required this.mineCount,
    required this.mines,
    required this.adjacent,
  });

  final int rows;
  final int cols;
  final int mineCount;

  /// 雷的位置，index = row * cols + col。
  final Set<int> mines;

  /// -1 表示雷；否则为相邻雷数。
  final List<List<int>> adjacent;

  int get total => rows * cols;

  bool isMine(int index) => mines.contains(index);

  bool isMineAt(int r, int c) {
    if (r < 0 || r >= rows || c < 0 || c >= cols) return false;
    return mines.contains(r * cols + c);
  }

  /// 越界返回 -1（与「雷」同值，调用方需先判断坐标）。
  int adjacentAt(int r, int c) {
    if (r < 0 || r >= rows || c < 0 || c >= cols) return -1;
    return adjacent[r][c];
  }

  /// 点开一格并扩散：0 格自动展开邻居；返回本次新开的所有 index。
  Set<int> reveal(int index) {
    if (isMine(index)) return {};
    final opened = <int>{};
    final stack = <int>[index];
    while (stack.isNotEmpty) {
      final cur = stack.removeLast();
      if (opened.contains(cur)) continue;
      if (isMine(cur)) continue;
      opened.add(cur);
      final r = cur ~/ cols;
      final c = cur % cols;
      if (adjacent[r][c] != 0) continue;
      for (var dr = -1; dr <= 1; dr++) {
        for (var dc = -1; dc <= 1; dc++) {
          if (dr == 0 && dc == 0) continue;
          final nr = r + dr;
          final nc = c + dc;
          if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) continue;
          final ni = nr * cols + nc;
          if (!opened.contains(ni) && !isMine(ni)) stack.add(ni);
        }
      }
    }
    return opened;
  }

  /// 所有非雷格都开完 → 通关。
  bool isCleared(Set<int> opened) {
    for (var i = 0; i < total; i++) {
      if (isMine(i)) continue;
      if (!opened.contains(i)) return false;
    }
    return true;
  }

  /// 通关后应显示的旗子：所有未点开的雷。
  /// 与玩家手动插错的旗一起看，保证「雷都被标出来了」。
  Set<int> victoryFlags(Set<int> opened, Set<int> userFlags) {
    final out = <int>{...userFlags};
    for (final m in mines) {
      if (!opened.contains(m)) out.add(m);
    }
    return out;
  }
}

/// 布雷时排除 [safeIndex]，保证首次点击不是雷。
MinesweeperBoard generateMinesweeper(
  String difficultyId, {
  required int safeIndex,
  Random? random,
}) {
  final spec = minesweeperSpecFor(difficultyId);
  final rnd = random ?? Random();
  final total = spec.rows * spec.cols;
  final candidates = List.generate(total, (i) => i)..remove(safeIndex);
  candidates.shuffle(rnd);
  final mines = candidates.take(spec.mines).toSet();

  final adjacent = List.generate(spec.rows, (_) => List.filled(spec.cols, 0));
  for (var r = 0; r < spec.rows; r++) {
    for (var c = 0; c < spec.cols; c++) {
      final i = r * spec.cols + c;
      if (mines.contains(i)) {
        adjacent[r][c] = -1;
        continue;
      }
      var n = 0;
      for (var dr = -1; dr <= 1; dr++) {
        for (var dc = -1; dc <= 1; dc++) {
          if (dr == 0 && dc == 0) continue;
          final nr = r + dr;
          final nc = c + dc;
          if (nr < 0 || nr >= spec.rows || nc < 0 || nc >= spec.cols) continue;
          if (mines.contains(nr * spec.cols + nc)) n++;
        }
      }
      adjacent[r][c] = n;
    }
  }

  return MinesweeperBoard(
    rows: spec.rows,
    cols: spec.cols,
    mineCount: spec.mines,
    mines: mines,
    adjacent: adjacent,
  );
}
