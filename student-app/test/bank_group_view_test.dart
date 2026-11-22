import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/question_grouping.dart';

void main() {
  test('按 group_id 分组并按 seq 排序', () {
    final qs = [
      BankQuestion.fromJson({'id': 3, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'c', 'options': [], 'group_id': 7, 'seq_in_group': 3,
        'group_stem': '直接写出得数'}),
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': [], 'group_id': 7, 'seq_in_group': 1,
        'group_stem': '直接写出得数'}),
      BankQuestion.fromJson({'id': 5, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'x', 'options': [], 'group_id': 8, 'seq_in_group': 1,
        'group_stem': '用竖式计算'}),
    ];
    final groups = groupBankQuestions(qs);
    expect(groups.length, 2);
    expect(groups[0].items.map((q) => q.id).toList(), [1, 3]);
    expect(groups[0].stem, '直接写出得数');
    expect(groups[1].items.map((q) => q.id).toList(), [5]);
  });

  test('示例与待做分开', () {
    final qs = [
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': [], 'group_id': 7, 'seq_in_group': 1,
        'is_example': true}),
      BankQuestion.fromJson({'id': 2, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'b', 'options': [], 'group_id': 7, 'seq_in_group': 2,
        'is_example': false}),
    ];
    final g = groupBankQuestions(qs).first;
    expect(g.examples.map((q) => q.id).toList(), [1]);
    expect(g.items.map((q) => q.id).toList(), [2]);
  });

  test('无 group_id 归到 legacy 组', () {
    final qs = [
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': []}),
      BankQuestion.fromJson({'id': 2, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'b', 'options': []}),
    ];
    final groups = groupBankQuestions(qs);
    expect(groups.length, 1);
    expect(groups[0].isLegacy, isTrue);
    expect(groups[0].items.length, 2);
  });
}
