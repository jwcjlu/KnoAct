import 'dart:convert';

/// 计算题（`GET /api/math/task/{id}/material` 的 `calc[]`）
class MathCalcItem {
  const MathCalcItem({
    required this.index,
    required this.question,
    this.id,
    this.yourAnswer = '',
    this.isCorrect,
  });

  factory MathCalcItem.fromJson(Map<String, dynamic> j) => MathCalcItem(
        index: (j['index'] as num?)?.toInt() ?? 0,
        question: '${j['question'] ?? ''}',
        id: j['id'] == null ? null : '${j['id']}',
        yourAnswer: '${j['your_answer'] ?? ''}',
        isCorrect: j['is_correct'] is bool ? j['is_correct'] as bool : null,
      );

  final int index;
  final String question;
  final String? id;
  final String yourAnswer;
  final bool? isCorrect;

  MathCalcItem copyWith({String? yourAnswer, bool? isCorrect}) => MathCalcItem(
        index: index,
        question: question,
        id: id,
        yourAnswer: yourAnswer ?? this.yourAnswer,
        isCorrect: isCorrect ?? this.isCorrect,
      );
}

/// 应用题（不下发标准答案；含拍照与 AI / 家长状态）
class MathWordItem {
  const MathWordItem({
    required this.index,
    required this.question,
    this.id,
    this.photoPath,
    this.aiStatus,
    this.parentStatus,
  });

  factory MathWordItem.fromJson(Map<String, dynamic> j) => MathWordItem(
        index: (j['index'] as num?)?.toInt() ?? 0,
        question: '${j['question'] ?? ''}',
        id: j['id'] == null ? null : '${j['id']}',
        photoPath: j['photo_path'] == null ? null : '${j['photo_path']}',
        aiStatus: j['ai_status'] == null ? null : '${j['ai_status']}',
        parentStatus: j['parent_status'] == null ? null : '${j['parent_status']}',
      );

  final int index;
  final String question;
  final String? id;
  final String? photoPath;
  final String? aiStatus;
  final String? parentStatus;

  bool get hasPhoto => (photoPath ?? '').trim().isNotEmpty;

  bool get aiFinished {
    final st = (aiStatus ?? '').trim();
    return st == 'ok' || st == 'pending_review' || st == 'failed';
  }

  MathWordItem copyWith({
    String? photoPath,
    String? aiStatus,
    String? parentStatus,
  }) =>
      MathWordItem(
        index: index,
        question: question,
        id: id,
        photoPath: photoPath ?? this.photoPath,
        aiStatus: aiStatus ?? this.aiStatus,
        parentStatus: parentStatus ?? this.parentStatus,
      );
}

class MathTaskMaterial {
  const MathTaskMaterial({
    this.title = '',
    this.detail = '',
    this.calc = const [],
    this.word = const [],
  });

  factory MathTaskMaterial.fromJson(Map<String, dynamic> j) {
    final calcRaw = j['calc'];
    final wordRaw = j['word'];
    return MathTaskMaterial(
      title: '${j['title'] ?? ''}',
      detail: '${j['detail'] ?? ''}',
      calc: calcRaw is List
          ? [for (final c in calcRaw.whereType<Map>()) MathCalcItem.fromJson(Map<String, dynamic>.from(c))]
          : const [],
      word: wordRaw is List
          ? [for (final w in wordRaw.whereType<Map>()) MathWordItem.fromJson(Map<String, dynamic>.from(w))]
          : const [],
    );
  }

  final String title;
  final String detail;
  final List<MathCalcItem> calc;
  final List<MathWordItem> word;

  bool get calcAllGraded => calc.isEmpty || calc.every((c) => c.isCorrect != null);

  bool get wordAllReady => word.isEmpty || word.every((w) => w.hasPhoto && w.aiFinished);
}

/// 孩子端应用题状态文案（不暴露 AI 对错）
String mathWordStatusLabel(MathWordItem w) {
  if (w.parentStatus == 'rejected') return '请重新拍照';
  if (!w.hasPhoto) return '请拍照上传作答过程与答案';
  if (!w.aiFinished) return '批改中…';
  if (w.parentStatus == 'approved') return '家长已确认';
  return '等待家长确认';
}

class MathGradeResult {
  const MathGradeResult({required this.correct, required this.total, required this.results});

  final int correct;
  final int total;
  final List<bool> results;

  factory MathGradeResult.fromJson(Map<String, dynamic> j) => MathGradeResult(
        correct: (j['correct'] as num?)?.toInt() ?? 0,
        total: (j['total'] as num?)?.toInt() ?? 0,
        results: [
          if (j['results'] is List)
            for (final r in (j['results'] as List).whereType<Map>()) r['is_correct'] == true,
        ],
      );
}

/// 旧版 flat JSON 列表 → 全计算题（本地兜底）
MathTaskMaterial parseMathLegacyContent(String content, {String title = ''}) {
  if (content.isEmpty) return MathTaskMaterial(title: title);
  try {
    final data = jsonDecode(content);
    if (data is! List) return MathTaskMaterial(title: title);
    final calc = <MathCalcItem>[];
    for (var i = 0; i < data.length; i++) {
      final q = data[i];
      if (q is! Map) continue;
      final m = Map<String, dynamic>.from(q);
      calc.add(MathCalcItem(
        index: i,
        question: '${m['question'] ?? ''}',
        id: m['id'] == null ? null : '${m['id']}',
        yourAnswer: '${m['your_answer'] ?? ''}',
        isCorrect: m['is_correct'] is bool ? m['is_correct'] as bool : null,
      ));
    }
    return MathTaskMaterial(title: title, calc: calc);
  } catch (_) {
    return MathTaskMaterial(title: title);
  }
}
