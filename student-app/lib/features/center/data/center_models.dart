class CenterQuestion {
  const CenterQuestion(this.question, this.answer);

  final String question;
  final String answer;
}

class CenterMaterial {
  const CenterMaterial({required this.text, required this.questions});

  factory CenterMaterial.fromJson(Map<String, dynamic> j) {
    final qs = j['questions'];
    return CenterMaterial(
      text: '${j['text'] ?? ''}',
      questions: [
        if (qs is List)
          for (final q in qs.whereType<Map>()) CenterQuestion('${q['question'] ?? ''}', '${q['answer'] ?? ''}'),
      ],
    );
  }

  static const empty = CenterMaterial(text: '', questions: []);

  final String text;
  final List<CenterQuestion> questions;

  bool get isEmpty => text.isEmpty || questions.isEmpty;
}
