import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';

void main() {
  test('解析题组字段', () {
    final q = BankQuestion.fromJson({
      'id': 12,
      'qtype': 'fill_blank',
      'qtype_category': 'blank',
      'question': r'$1111.05 \div 0.9 =$ ____',
      'options': [],
      'group_id': 7,
      'group_stem': '不计算，运用规律直接写出得数',
      'seq_in_group': 4,
      'is_example': false,
      'work_mode': 'pattern',
      'input_ui': 'keypad',
      'answer_kind': 'numeric_list',
      'answer': '1234.5, 12345',
      'blank_count': 2,
    });
    expect(q.groupId, 7);
    expect(q.groupStem, '不计算，运用规律直接写出得数');
    expect(q.seqInGroup, 4);
    expect(q.isExample, isFalse);
    expect(q.workMode, 'pattern');
    expect(q.inputUi, 'keypad');
    expect(q.answerKind, 'numeric_list');
    expect(q.answer, '1234.5, 12345');
    expect(q.blankCount, 2);
  });

  test('缺字段时给安全默认值（兼容旧接口）', () {
    final q = BankQuestion.fromJson({
      'id': 1, 'qtype': 'short_answer', 'qtype_category': 'subjective',
      'question': '旧题', 'options': [],
    });
    expect(q.groupId, isNull);
    expect(q.groupStem, '');
    expect(q.seqInGroup, 0);
    expect(q.isExample, isFalse);
    expect(q.workMode, '');
    expect(q.inputUi, '');
    expect(q.answerKind, '');
    expect(q.answer, '');
    expect(q.blankCount, 1); // 默认单空
  });

  test('示例行标记', () {
    final q = BankQuestion.fromJson({
      'id': 2, 'qtype': 'fill_blank', 'qtype_category': 'blank',
      'question': r'$1.08 \div 0.9 = 1.2$', 'options': [], 'is_example': true,
    });
    expect(q.isExample, isTrue);
  });
}
