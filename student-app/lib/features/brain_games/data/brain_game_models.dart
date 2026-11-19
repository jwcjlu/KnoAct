/// 三个思维训练游戏。
enum BrainGameKind {
  sudoku('sudoku', '数独'),
  schulte('schulte', '舒尔特方格'),
  minesweeper('minesweeper', '数字扫雷');

  const BrainGameKind(this.id, this.label);
  final String id;
  final String label;
}

/// 难度，孩子在游戏内自选。
enum BrainGameDifficulty {
  easy('easy', '简单'),
  medium('medium', '中等'),
  hard('hard', '困难');

  const BrainGameDifficulty(this.id, this.label);
  final String id;
  final String label;
}

/// 路由路径与枚举的对应关系。
class GameKindRoute {
  static String pathOf(BrainGameKind kind) => '/brain-games/${kind.id}';

  static BrainGameKind? fromPath(String path) {
    for (final k in BrainGameKind.values) {
      if (pathOf(k) == path) return k;
    }
    return null;
  }
}

/// 某游戏某难度的历史成绩。
class DifficultyStat {
  const DifficultyStat({
    required this.bestMs,
    required this.played,
    required this.solved,
  });

  /// 通关最小用时；从未通关为 null。
  final int? bestMs;
  final int played;
  final int solved;

  factory DifficultyStat.fromJson(Map<String, dynamic> j) => DifficultyStat(
    bestMs: (j['best_ms'] as num?)?.toInt(),
    played: (j['played'] as num?)?.toInt() ?? 0,
    solved: (j['solved'] as num?)?.toInt() ?? 0,
  );
}

/// stats 的三层结构：game → difficulty → stat
typedef BrainGameStats =
    Map<BrainGameKind, Map<BrainGameDifficulty, DifficultyStat>>;
