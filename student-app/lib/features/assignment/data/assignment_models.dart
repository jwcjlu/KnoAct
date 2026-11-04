class AssignmentQuestion {
  const AssignmentQuestion({required this.question, required this.answer, this.knowledgePointId});

  factory AssignmentQuestion.fromJson(Map<String, dynamic> j) => AssignmentQuestion(
        question: '${j['question'] ?? ''}',
        answer: '${j['answer'] ?? ''}',
        knowledgePointId: (j['knowledge_point_id'] as num?)?.toInt(),
      );

  final String question;
  final String answer;
  final int? knowledgePointId;
}

List<AssignmentQuestion> parseQuestions(Object? data) {
  final qs = (data is Map ? data['questions'] : null);
  if (qs is! List) return const [];
  return [for (final q in qs.whereType<Map>()) AssignmentQuestion.fromJson(Map<String, dynamic>.from(q))];
}

/// 判分后单题结果
class AssignmentGradeItem {
  const AssignmentGradeItem({
    required this.question,
    required this.answer,
    required this.studentAnswer,
    required this.isCorrect,
    required this.feedback,
  });

  factory AssignmentGradeItem.fromJson(Map<String, dynamic> j) => AssignmentGradeItem(
        question: '${j['question'] ?? ''}',
        answer: '${j['answer'] ?? ''}',
        studentAnswer: '${j['student_answer'] ?? ''}',
        isCorrect: j['is_correct'] == true,
        feedback: '${j['feedback'] ?? ''}',
      );

  final String question;
  final String answer;
  final String studentAnswer;
  final bool isCorrect;
  final String feedback;
}

/// 判分结果
class AssignmentResult {
  const AssignmentResult({
    required this.passed,
    required this.rate,
    required this.threshold,
    required this.correct,
    required this.total,
    required this.items,
  });

  factory AssignmentResult.fromJson(Map<String, dynamic> j) => AssignmentResult(
        passed: j['passed'] == true,
        rate: (j['rate'] as num?)?.toDouble() ?? 0,
        threshold: (j['threshold'] as num?)?.toDouble() ?? 0.6,
        correct: (j['correct'] as num?)?.toInt() ?? 0,
        total: (j['total'] as num?)?.toInt() ?? 0,
        items: [
          if (j['results'] is List)
            for (final r in (j['results'] as List).whereType<Map>())
              AssignmentGradeItem.fromJson(Map<String, dynamic>.from(r)),
        ],
      );

  final bool passed;
  final double rate;
  final double threshold;
  final int correct;
  final int total;
  final List<AssignmentGradeItem> items;
}
