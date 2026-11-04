class CenterQuestion {
  const CenterQuestion(this.question, this.answer);

  final String question;
  final String answer;
}

class CenterMaterial {
  const CenterMaterial({required this.text, required this.questions, this.lessonId});

  factory CenterMaterial.fromJson(Map<String, dynamic> j, {int? lessonId}) {
    final qs = j['questions'];
    return CenterMaterial(
      text: '${j['text'] ?? ''}',
      questions: [
        if (qs is List)
          for (final q in qs.whereType<Map>()) CenterQuestion('${q['question'] ?? ''}', '${q['answer'] ?? ''}'),
      ],
      lessonId: lessonId,
    );
  }

  static const empty = CenterMaterial(text: '', questions: []);

  final String text;
  final List<CenterQuestion> questions;

  /// 当前阅读课的 id；「边读边问」和「做作业」需要它（听力材料无 lesson）
  final int? lessonId;

  bool get isEmpty => text.isEmpty || questions.isEmpty;
}
