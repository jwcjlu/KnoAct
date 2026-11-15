import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/question_html.dart';

void main() {
  test('解析 br 与 img，剥离脚本标签', () {
    final tokens = tokenizeQuestionHtml(
      '在数线上标出\$908000\$<br/>'
      '<img src="https://img.cuotixue.com/a.jpg" style="vertical-align:middle">'
      '<script>alert(1)</script>',
    );
    expect(tokens.map((t) => t.kind).toList(), ['text', 'br', 'img']);
    expect(tokens[0].text, '在数线上标出908000');
    expect(tokens[2].text, 'https://img.cuotixue.com/a.jpg');
    expect(tokens.any((t) => t.text.contains('alert')), isFalse);
  });

  test('选项里的 img+br+文本', () {
    final tokens = tokenizeQuestionHtml(
      '<img src="https://img.example.com/x.png" style="float:none;"><br>三角形面积为\$1\$',
    );
    expect(tokens.map((t) => t.kind).toList(), ['img', 'br', 'text']);
    expect(tokens[0].text, 'https://img.example.com/x.png');
    expect(tokens[2].text, '三角形面积为1');
  });

  test('拒绝非 http(s) 图片地址', () {
    final tokens = tokenizeQuestionHtml('<img src="javascript:alert(1)">安全');
    expect(tokens.any((t) => t.kind == 'img'), isFalse);
    expect(tokens.map((t) => t.text).join(), contains('安全'));
  });

  test('纯文本原样保留', () {
    final tokens = tokenizeQuestionHtml('1+1=?');
    expect(tokens, hasLength(1));
    expect(tokens.first.kind, 'text');
    expect(tokens.first.text, '1+1=?');
  });

  test('解码常见实体并展开 u/b/p', () {
    final tokens = tokenizeQuestionHtml('<p>看&nbsp;<b>图</b></p>');
    expect(tokens.map((t) => t.text).join(), '看 图');
  });

  test('学库宝真实题干：img 后双空格仍解析', () {
    const raw =
        '如图是一个有盖的长方体纸盒的展开图,求它的体积.<br/><img  src="https://img.cuotixue.com/tikuimages/x.jpg" style="vertical-align:middle">';
    final tokens = tokenizeQuestionHtml(raw);
    expect(tokens.map((t) => t.kind).toList(), ['text', 'br', 'img']);
    expect(tokens[2].text, 'https://img.cuotixue.com/tikuimages/x.jpg');
  });
}
