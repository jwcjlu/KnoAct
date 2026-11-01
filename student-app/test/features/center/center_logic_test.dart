import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';

void main() {
  bool check({CenterTab? taskTab = CenterTab.reading, CenterTab current = CenterTab.reading, int count = 2, int answered = 2, bool submitting = false}) =>
      shouldAutoSubmit(taskTab: taskTab, currentTab: current, questionCount: count, answeredCount: answered, submitting: submitting);

  test('自动提交条件', () {
    expect(check(), isTrue);
    expect(check(taskTab: null), isFalse);
    expect(check(current: CenterTab.listening), isFalse);
    expect(check(count: 0, answered: 0), isFalse);
    expect(check(answered: 1), isFalse);
    expect(check(submitting: true), isFalse);
  });

  test('答案比对去首尾空白后全等', () {
    expect(isCorrectAnswer(' 相等 ', '相等'), isTrue);
    expect(isCorrectAnswer('不相等', '相等'), isFalse);
  });

  test('材料解析与空材料', () {
    final m = CenterMaterial.fromJson({
      'text': 'Hello.\nHi.',
      'questions': [{'question': 'Q1', 'answer': 'A1'}],
    });
    expect(m.text, 'Hello.\nHi.');
    expect(m.questions.single.question, 'Q1');
    expect(m.isEmpty, isFalse);
    expect(CenterMaterial.fromJson({'text': '', 'questions': []}).isEmpty, isTrue);
    expect(CenterMaterial.empty.questions, isEmpty);
  });

  test('朗读语言：含英文字母用 en-US', () {
    expect(speechLanguage('Hello'), 'en-US');
    expect(speechLanguage('你好'), 'zh-CN');
  });
}
