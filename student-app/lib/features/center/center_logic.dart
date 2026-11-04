export '../../core/text_utils.dart' show splitSentences;

enum CenterTab { listening, reading }

extension CenterTabX on CenterTab {
  String get label => this == CenterTab.listening ? '听力理解' : '阅读理解';
  String get sourceType => this == CenterTab.listening ? 'listening' : 'reading';
}

/// 仅当在任务对应的 Tab、题目数 > 0、全部作答且不在提交中时自动提交任务
bool shouldAutoSubmit({
  required CenterTab? taskTab,
  required CenterTab currentTab,
  required int questionCount,
  required int answeredCount,
  required bool submitting,
}) =>
    taskTab != null && taskTab == currentTab && questionCount > 0 && answeredCount >= questionCount && !submitting;

bool isCorrectAnswer(String input, String answer) => input.trim() == answer.trim();

String speechLanguage(String text) => RegExp('[a-zA-Z]').hasMatch(text) ? 'en-US' : 'zh-CN';
