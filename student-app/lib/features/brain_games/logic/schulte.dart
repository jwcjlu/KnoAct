import 'dart:math';

/// 舒尔特方格难度 → 边长。
int schulteSizeFor(String difficultyId) => switch (difficultyId) {
  'medium' => 4,
  'hard' => 5,
  _ => 3,
};

class SchulteBoard {
  SchulteBoard({required this.size, required this.numbers});

  final int size;

  /// 按行优先铺开的乱序数字（1..size²）。
  final List<int> numbers;

  int get max => size * size;

  /// 已点掉的数字集合 == 全部数字 → 通关。
  bool isComplete(Set<int> cleared) =>
      cleared.length >= max &&
      cleared.containsAll(List.generate(max, (i) => i + 1));
}

SchulteBoard generateSchulte(String difficultyId, {Random? random}) {
  final size = schulteSizeFor(difficultyId);
  final n = size * size;
  final numbers = List.generate(n, (i) => i + 1)..shuffle(random ?? Random());
  return SchulteBoard(size: size, numbers: numbers);
}
