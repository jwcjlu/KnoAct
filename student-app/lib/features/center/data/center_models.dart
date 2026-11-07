class CenterQuestion {
  const CenterQuestion(
    this.question,
    this.answer, {
    this.options = const [],
    this.correctIndex,
  });

  final String question;
  final String answer;
  final List<String> options;
  final int? correctIndex;

  bool get isMultipleChoice => options.length >= 4 && correctIndex != null;
}

class CenterMaterial {
  const CenterMaterial({required this.text, required this.questions, this.lessonId});

  factory CenterMaterial.fromJson(Map<String, dynamic> j, {int? lessonId}) {
    final qs = j['questions'];
    return CenterMaterial(
      text: '${j['text'] ?? ''}',
      questions: [
        if (qs is List) for (final q in qs.whereType<Map>()) _questionFromJson(q),
      ],
      lessonId: lessonId,
    );
  }

  static CenterQuestion _questionFromJson(Map q) {
    var optionsRaw = q['options'] ?? q['choices'];
    final options = optionsRaw is List ? [for (final o in optionsRaw) '$o'] : <String>[];
    int? correctIndex;
    final ci = q['correct_index'] ?? q['correctIndex'];
    if (ci is num) {
      correctIndex = ci.toInt();
    } else if (ci is String) {
      correctIndex = int.tryParse(ci.trim());
    }
    var answer = '${q['answer'] ?? ''}';
    if (answer.isEmpty && correctIndex != null && correctIndex >= 0 && correctIndex < options.length) {
      answer = options[correctIndex];
    }
    return CenterQuestion(
      '${q['question'] ?? ''}',
      answer,
      options: options,
      correctIndex: correctIndex,
    );
  }

  static const empty = CenterMaterial(text: '', questions: []);

  final String text;
  final List<CenterQuestion> questions;

  /// 当前阅读课的 id；「边读边问」和「做作业」需要它（听力材料无 lesson）
  final int? lessonId;

  bool get isEmpty => text.isEmpty || questions.isEmpty;
}
