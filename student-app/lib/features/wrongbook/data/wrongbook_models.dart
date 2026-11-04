import '../../../core/api_client.dart';

class MistakeItem {
  const MistakeItem({
    required this.id,
    required this.sourceType,
    required this.question,
    required this.yourAnswer,
    required this.correctAnswer,
    required this.mistakeCount,
    required this.consecutiveCorrect,
  });

  factory MistakeItem.fromJson(Map<String, dynamic> j) => MistakeItem(
        id: (j['id'] as num).toInt(),
        sourceType: '${j['source_type'] ?? ''}',
        question: '${j['question'] ?? ''}',
        yourAnswer: '${j['your_answer'] ?? ''}',
        correctAnswer: '${j['correct_answer'] ?? ''}',
        mistakeCount: (j['mistake_count'] as num?)?.toInt() ?? 0,
        consecutiveCorrect: (j['consecutive_correct'] as num?)?.toInt() ?? 0,
      );

  final int id;
  final String sourceType;
  final String question;
  final String yourAnswer;
  final String correctAnswer;
  final int mistakeCount;
  final int consecutiveCorrect;
}

/// 来源类型 → 中文名（对齐旧版前端 srcName）
const mistakeSourceNames = {
  'dictation': '生词听写',
  'review': '基础知识复习',
  'listening': '单词听写',
  'reading': '阅读理解',
  'goal': '目标考核',
  'math': '数学练习',
};

/// source_type → 学科（对齐后端 _subject_sources：dictation/reading=语文，dictation/listening=英语）
String mistakeSubject(String sourceType) {
  if (sourceType == 'math') return '数学';
  if (sourceType == 'reading') return '语文';
  if (sourceType == 'listening') return '英语';
  if (sourceType == 'dictation') return '语文';
  if (sourceType == 'review' || sourceType == 'goal') return '语文';
  return '语文';
}

/// 解析 /api/mistakes 返回的列表
List<MistakeItem> parseMistakes(Object? data) {
  final list = asList(data);
  return [for (final m in list.whereType<Map>()) MistakeItem.fromJson(Map<String, dynamic>.from(m))];
}
