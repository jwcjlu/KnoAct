import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/math_exercise/data/math_models.dart';

void main() {
  test('MathTaskMaterial parses calc and word without answers', () {
    final m = MathTaskMaterial.fromJson({
      'title': '数学练习',
      'detail': '加油',
      'calc': [
        {'index': 0, 'question': '3+5=？', 'your_answer': '8', 'is_correct': true},
      ],
      'word': [
        {
          'index': 0,
          'id': 'w1',
          'question': '小明有 3 个苹果…',
          'photo_path': 'uploads/x.jpg',
          'ai_status': 'pending_review',
          'parent_status': 'none',
        },
      ],
    });
    expect(m.title, '数学练习');
    expect(m.calc, hasLength(1));
    expect(m.calc.first.question, '3+5=？');
    expect(m.calc.first.isCorrect, isTrue);
    expect(m.word, hasLength(1));
    expect(m.word.first.hasPhoto, isTrue);
    expect(m.word.first.aiFinished, isTrue);
    expect(m.calcAllGraded, isTrue);
    expect(m.wordAllReady, isTrue);
  });

  test('mathWordStatusLabel hides AI verdict', () {
    const w = MathWordItem(
      index: 0,
      question: 'q',
      photoPath: 'p.jpg',
      aiStatus: 'ok',
      parentStatus: 'none',
    );
    expect(mathWordStatusLabel(w), '等待家长确认');
    expect(mathWordStatusLabel(w.copyWith(parentStatus: 'rejected')), '请重新拍照');
    expect(mathWordStatusLabel(const MathWordItem(index: 0, question: 'q')), '请拍照上传作答过程与答案');
  });

  test('parseMathLegacyContent treats flat list as calc', () {
    final m = parseMathLegacyContent(
      '[{"question":"1+1=？","answer":"2","your_answer":"2","is_correct":true}]',
      title: '旧任务',
    );
    expect(m.calc, hasLength(1));
    expect(m.word, isEmpty);
    expect(m.calc.first.isCorrect, isTrue);
  });

  test('MathGradeResult maps backend payload', () {
    final r = MathGradeResult.fromJson({
      'correct': 2,
      'total': 3,
      'results': [
        {'is_correct': true},
        {'is_correct': false},
        {'is_correct': true},
      ],
    });
    expect(r.correct, 2);
    expect(r.results, [true, false, true]);
  });
}
