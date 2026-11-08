import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/passage_markup.dart';

void main() {
  test('tokenize 加粗、音标、挖空', () {
    final tokens = tokenizePassage('**生词** /ˈæpl/ ____');
    final kinds = tokens.map((t) => t.kind).toList();
    expect(kinds, containsAllInOrder(['bold', 'ipa', 'blank']));
    expect(tokens.firstWhere((t) => t.kind == 'bold').text, '生词');
    expect(tokens.firstWhere((t) => t.kind == 'ipa').text, 'ˈæpl');
  });

  test('tokenize 标题行', () {
    final tokens = tokenizePassage('# 标题\n正文');
    expect(tokens.first.kind, 'h1');
    expect(tokens.first.text, '标题');
  });

  test('白名单外当纯文本', () {
    final tokens = tokenizePassage('[link](http://x) and `code`');
    expect(tokens.every((t) => t.kind == 'text' || t.kind == 'br'), isTrue);
    expect(tokens.map((t) => t.text).join(), contains('[link](http://x)'));
  });

  test('下划线标签', () {
    final tokens = tokenizePassage('<u>line</u>');
    expect(tokens.any((t) => t.kind == 'underline' && t.text == 'line'), isTrue);
  });
}
