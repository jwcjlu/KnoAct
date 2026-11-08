class PracticeBank {
  const PracticeBank({
    required this.id,
    required this.title,
    required this.subject,
    required this.questionCount,
    this.grade,
  });

  final int id;
  final String title;
  final String subject;
  final int? grade;
  final int questionCount;

  factory PracticeBank.fromJson(Map<String, dynamic> json) => PracticeBank(
        id: (json['id'] as num?)?.toInt() ?? 0,
        title: '${json['title'] ?? ''}',
        subject: '${json['subject'] ?? ''}',
        grade: (json['grade'] as num?)?.toInt(),
        questionCount: (json['question_count'] as num?)?.toInt() ?? 0,
      );
}

class BankQuestion {
  const BankQuestion({
    required this.id,
    required this.qtype,
    required this.qtypeCategory,
    required this.question,
    required this.options,
    this.analysis = '',
  });

  final int id;
  final String qtype;
  final String qtypeCategory;
  final String question;
  final List<BankOption> options;
  final String analysis;

  factory BankQuestion.fromJson(Map<String, dynamic> json) {
    final optsRaw = json['options'];
    final opts = <BankOption>[];
    if (optsRaw is List) {
      for (final o in optsRaw) {
        if (o is Map) opts.add(BankOption.fromJson(Map<String, dynamic>.from(o)));
      }
    }
    return BankQuestion(
      id: (json['id'] as num?)?.toInt() ?? 0,
      qtype: '${json['qtype'] ?? ''}',
      qtypeCategory: '${json['qtype_category'] ?? ''}',
      question: '${json['question'] ?? ''}',
      options: opts,
      analysis: '${json['analysis'] ?? ''}',
    );
  }
}

class BankOption {
  const BankOption({required this.label, required this.value});

  final String label;
  final int value;

  factory BankOption.fromJson(Map<String, dynamic> json) => BankOption(
        label: '${json['label'] ?? ''}',
        value: (json['value'] as num?)?.toInt() ?? 0,
      );
}

class BankAnswerResult {
  const BankAnswerResult({
    required this.questionId,
    required this.isCorrect,
    this.correctAnswerText = '',
    this.detail = '',
  });

  final int questionId;
  final bool? isCorrect;
  final String correctAnswerText;
  final String detail;

  factory BankAnswerResult.fromJson(Map<String, dynamic> json) => BankAnswerResult(
        questionId: (json['question_id'] as num?)?.toInt() ?? 0,
        isCorrect: json['is_correct'] as bool?,
        correctAnswerText: '${json['correct_answer_text'] ?? ''}',
        detail: '${json['detail'] ?? ''}',
      );
}

class BankSubmitResult {
  const BankSubmitResult({required this.score, required this.total, required this.answers});

  final int score;
  final int total;
  final List<BankAnswerResult> answers;

  factory BankSubmitResult.fromJson(Map<String, dynamic> json) {
    final raw = json['answers'];
    final list = <BankAnswerResult>[];
    if (raw is List) {
      for (final a in raw) {
        if (a is Map) list.add(BankAnswerResult.fromJson(Map<String, dynamic>.from(a)));
      }
    }
    return BankSubmitResult(
      score: (json['score'] as num?)?.toInt() ?? 0,
      total: (json['total'] as num?)?.toInt() ?? list.length,
      answers: list,
    );
  }
}
