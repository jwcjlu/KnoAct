import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';

void main() {
  test('多空题 blankCount 来自后端', () {
    final q = BankQuestion.fromJson({
      'id': 1, 'qtype': 'fill_blank', 'qtype_category': 'blank',
      'question': r'$1111.05 \div 0.9 =$ ____', 'options': [],
      'work_mode': 'pattern', 'answer_kind': 'numeric_list',
      'answer': '1234.5, 12345', 'blank_count': 2,
    });
    expect(q.blankCount, 2);
  });

  test('单空题 blankCount 为 1', () {
    final q = BankQuestion.fromJson({
      'id': 2, 'qtype': 'calculation', 'qtype_category': 'blank',
      'question': r'$8.9 + 4.5 =$', 'options': [],
      'work_mode': 'oral', 'answer_kind': 'number', 'answer': '13.4',
      'blank_count': 1,
    });
    expect(q.blankCount, 1);
  });

  test('答案本身含逗号时不靠切分推断空数', () {
    // 若用 answer.split(',') 会得到 2 个空，错误；必须信后端 blank_count
    final q = BankQuestion.fromJson({
      'id': 3, 'qtype': 'fill_blank', 'qtype_category': 'blank',
      'question': 'x', 'options': [], 'answer': '1,234', 'blank_count': 1,
    });
    expect(q.blankCount, 1);
  });
}
