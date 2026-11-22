import 'data/bank_models.dart';

/// 一个题组：题干 + 示例行 + 待做小题。
class QuestionGroup {
  QuestionGroup({
    required this.groupId,
    required this.stem,
    required this.examples,
    required this.items,
  });

  final int? groupId;
  final String stem;
  final List<BankQuestion> examples;
  final List<BankQuestion> items;

  /// 没有任何题干也没有示例的历史题，按平铺处理。
  bool get isLegacy => groupId == null && stem.isEmpty;
}

/// 把扁平题目按 group_id 聚组；示例与待做分开，组内按 seq_in_group 排序。
List<QuestionGroup> groupBankQuestions(List<BankQuestion> list) {
  final map = <String, List<BankQuestion>>{};
  for (final q in list) {
    final key = q.groupId?.toString() ?? 'legacy';
    map.putIfAbsent(key, () => []).add(q);
  }
  final out = <QuestionGroup>[];
  for (final entry in map.entries) {
    // List.sort 不稳定（>32 项），seq 相同（如历史题全为 0）时按原顺序
    final order = {for (var i = 0; i < entry.value.length; i++) entry.value[i]: i};
    final all = entry.value
      ..sort((a, b) {
        final c = a.seqInGroup.compareTo(b.seqInGroup);
        return c != 0 ? c : order[a]!.compareTo(order[b]!);
      });
    final first = all.first;
    out.add(QuestionGroup(
      groupId: first.groupId,
      stem: first.groupStem,
      examples: all.where((q) => q.isExample).toList(),
      items: all.where((q) => !q.isExample).toList(),
    ));
  }
  return out;
}
