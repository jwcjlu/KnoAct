class ReaderQuizQuestion {
  const ReaderQuizQuestion({required this.id, required this.prompt, required this.choices});

  final String id;
  final String prompt;
  final List<String> choices;

  static ReaderQuizQuestion? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final id = '${raw['id'] ?? ''}';
    final prompt = '${raw['prompt'] ?? ''}';
    final choices = raw['choices'];
    if (id.isEmpty || prompt.isEmpty || choices is! List) return null;
    return ReaderQuizQuestion(
      id: id,
      prompt: prompt,
      choices: [for (final c in choices) '$c'],
    );
  }
}

class ReaderQuizGradeRow {
  const ReaderQuizGradeRow({
    required this.questionId,
    required this.isCorrect,
    this.correctIndex,
    this.selectedIndex,
  });

  final String questionId;
  final bool isCorrect;
  final int? correctIndex;
  final int? selectedIndex;

  static ReaderQuizGradeRow? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final qid = '${raw['question_id'] ?? ''}';
    return ReaderQuizGradeRow(
      questionId: qid,
      isCorrect: raw['is_correct'] == true,
      correctIndex: raw['correct_index'] is num ? (raw['correct_index'] as num).toInt() : null,
      selectedIndex: raw['selected_index'] is num ? (raw['selected_index'] as num).toInt() : null,
    );
  }
}

class DiagnosticQuestion {
  const DiagnosticQuestion({required this.id, required this.prompt, required this.options});

  final String id;
  final String prompt;
  final List<DiagnosticOption> options;

  static DiagnosticQuestion? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final id = '${raw['id'] ?? ''}';
    final prompt = '${raw['prompt'] ?? ''}';
    if (id.isEmpty || prompt.isEmpty) return null;
    final opts = raw['options'];
    final options = <DiagnosticOption>[];
    if (opts is List) {
      for (final o in opts) {
        if (o is Map && o['label'] != null) {
          options.add(DiagnosticOption(label: '${o['label']}'));
        }
      }
    }
    return DiagnosticQuestion(id: id, prompt: prompt, options: options);
  }
}

class DiagnosticOption {
  const DiagnosticOption({required this.label});

  final String label;
}
