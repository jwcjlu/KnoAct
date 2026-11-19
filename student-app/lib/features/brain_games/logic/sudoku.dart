import 'dart:math';

/// 一档数独的盘面规格。
class SudokuSpec {
  const SudokuSpec({
    required this.size,
    required this.boxRows,
    required this.boxCols,
    required this.givens,
  });

  final int size; // 4 / 6 / 9
  final int boxRows; // 宫内行数
  final int boxCols; // 宫内列数
  final int givens; // 保留的提示数
}

const _specs = <String, SudokuSpec>{
  'easy': SudokuSpec(size: 4, boxRows: 2, boxCols: 2, givens: 8),
  'medium': SudokuSpec(size: 6, boxRows: 2, boxCols: 3, givens: 14),
  'hard': SudokuSpec(size: 9, boxRows: 3, boxCols: 3, givens: 34),
};

/// 按难度 id 取规格；未知难度回落 easy。
SudokuSpec sudokuSpecFor(String difficultyId) =>
    _specs[difficultyId] ?? _specs['easy']!;

class SudokuPuzzle {
  SudokuPuzzle({
    required this.spec,
    required this.givens,
    required this.solution,
  });

  final SudokuSpec spec;

  /// 0 表示空格。
  final List<List<int>> givens;
  final List<List<int>> solution;

  bool isGiven(int row, int col) => givens[row][col] != 0;

  /// 全部填满（无 0）且与解完全一致才通关。
  bool isSolved(List<List<int>> grid) {
    for (var r = 0; r < spec.size; r++) {
      for (var c = 0; c < spec.size; c++) {
        if (grid[r][c] == 0 || grid[r][c] != solution[r][c]) return false;
      }
    }
    return true;
  }
}

List<List<int>> _empty(int size) =>
    List.generate(size, (_) => List.filled(size, 0));

bool _canPlace(List<List<int>> g, SudokuSpec spec, int r, int c, int v) {
  for (var i = 0; i < spec.size; i++) {
    if (g[r][i] == v || g[i][c] == v) return false;
  }
  final br = (r ~/ spec.boxRows) * spec.boxRows;
  final bc = (c ~/ spec.boxCols) * spec.boxCols;
  for (var i = 0; i < spec.boxRows; i++) {
    for (var j = 0; j < spec.boxCols; j++) {
      if (g[br + i][bc + j] == v) return false;
    }
  }
  return true;
}

/// 回溯填满整个盘面（每步候选值随机打乱，保证每次不同）。
bool _fill(List<List<int>> g, SudokuSpec spec, int pos, Random rnd) {
  final n = spec.size;
  if (pos == n * n) return true;
  final r = pos ~/ n;
  final c = pos % n;
  final candidates = List.generate(n, (i) => i + 1)..shuffle(rnd);
  for (final v in candidates) {
    if (!_canPlace(g, spec, r, c, v)) continue;
    g[r][c] = v;
    if (_fill(g, spec, pos + 1, rnd)) return true;
    g[r][c] = 0;
  }
  return false;
}

/// 生成一道题：先造完整解，再随机挖洞到 [SudokuSpec.givens] 个提示数。
/// 不校验唯一解（小学生场景，唯一解非必需）。
SudokuPuzzle generateSudoku(String difficultyId, {Random? random}) {
  final spec = sudokuSpecFor(difficultyId);
  final rnd = random ?? Random();
  final solution = _empty(spec.size);
  _fill(solution, spec, 0, rnd);

  final givens = [for (final row in solution) List<int>.from(row)];
  final cells = List.generate(spec.size * spec.size, (i) => i)..shuffle(rnd);
  var remaining = spec.size * spec.size;
  for (final idx in cells) {
    if (remaining <= spec.givens) break;
    givens[idx ~/ spec.size][idx % spec.size] = 0;
    remaining--;
  }
  return SudokuPuzzle(spec: spec, givens: givens, solution: solution);
}
