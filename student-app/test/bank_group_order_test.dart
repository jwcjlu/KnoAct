import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/question_grouping.dart';

void main() {
  test('legacy 组（seq 全为 0）保持原始顺序，50+ 项也不乱', () {
    // 造 60 道无 group_id 的旧题，seqInGroup 全是 0
    final qs = [
      for (var i = 0; i < 60; i++)
        BankQuestion.fromJson({
          'id': i + 1, 'qtype': 'short_answer', 'qtype_category': 'subjective',
          'question': '旧题$i', 'options': [],
        }),
    ];
    final groups = groupBankQuestions(qs);
    expect(groups.length, 1);
    final ids = groups.first.items.map((q) => q.id).toList();
    expect(ids, List.generate(60, (i) => i + 1),
        reason: 'List.sort 不稳定，必须显式保序');
  });

  test('同 seq 的题保序', () {
    final qs = [
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': [], 'group_id': 7, 'seq_in_group': 0}),
      BankQuestion.fromJson({'id': 2, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'b', 'options': [], 'group_id': 7, 'seq_in_group': 0}),
      BankQuestion.fromJson({'id': 3, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'c', 'options': [], 'group_id': 7, 'seq_in_group': 0}),
    ];
    final g = groupBankQuestions(qs).first;
    expect(g.items.map((q) => q.id).toList(), [1, 2, 3]);
  });
}
