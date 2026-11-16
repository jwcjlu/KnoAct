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
    expect(
      tokens.where((t) => t.kind == 'text').map((t) => t.text).join(),
      '看 图',
    );
  });

  test('学库宝真实题干：img 后双空格仍解析', () {
    const raw =
        '如图是一个有盖的长方体纸盒的展开图,求它的体积.<br/><img  src="https://img.cuotixue.com/tikuimages/x.jpg" style="vertical-align:middle">';
    final tokens = tokenizeQuestionHtml(raw);
    expect(tokens.map((t) => t.kind).toList(), ['text', 'br', 'img']);
    expect(tokens[2].text, 'https://img.cuotixue.com/tikuimages/x.jpg');
  });

  test('p 标签拆成段落块', () {
    final tokens = tokenizeQuestionHtml('<p>第一段</p><p>第二段</p>');
    final blocks = splitQuestionHtmlBlocks(tokens);
    expect(blocks, hasLength(2));
    expect(blocks[0].single.text, '第一段');
    expect(blocks[1].single.text, '第二段');
  });

  test('语文阅读 br 分段并识别体裁角色', () {
    const raw =
        '阅读.<br/>金秋的桂花<br/>①桂花开了。<br/>②香气四溢。<br/>（1）写出三个方面。<br/>A．颜色<br/>B．形状';
    final blocks = splitQuestionHtmlBlocks(tokenizeQuestionHtml(raw));
    final kinds = classifyQuestionHtmlBlocks(blocks);
    expect(blocks.length, greaterThanOrEqualTo(6));
    expect(kinds[0], QuestionHtmlBlockKind.lead);
    expect(kinds[1], QuestionHtmlBlockKind.title);
    expect(kinds[2], QuestionHtmlBlockKind.passage);
    expect(kinds[4], QuestionHtmlBlockKind.subQuestion);
    expect(kinds[5], QuestionHtmlBlockKind.option);
  });

  test('无圈号段落的阅读材料也能分段并区分小题', () {
    const raw = '春望<br/>'
        '国破山河在，城春草木深。感时花溅泪，恨别鸟惊心。<br/>'
        '烽火连三月，家书抵万金。白头搔更短，浑欲不胜簪。<br/>'
        '1.这首诗的作者是谁？<br/>'
        '2.写出诗中的一对对偶句。';
    final blocks = splitQuestionHtmlBlocks(tokenizeQuestionHtml(raw));
    final kinds = classifyQuestionHtmlBlocks(blocks);
    expect(kinds[0], QuestionHtmlBlockKind.title);
    expect(kinds[1], QuestionHtmlBlockKind.passage);
    expect(kinds[2], QuestionHtmlBlockKind.passage);
    expect(kinds[3], QuestionHtmlBlockKind.subQuestion);
    expect(kinds[4], QuestionHtmlBlockKind.subQuestion);
  });

  test('材料区短句不会被误标成居中标题', () {
    const raw = '荷塘月色<br/>曲曲折折的荷塘上面，弥望的是田田的叶子。<br/>月光如流水。<br/>（1）作者是谁？';
    final kinds = classifyQuestionHtmlBlocks(splitQuestionHtmlBlocks(tokenizeQuestionHtml(raw)));
    expect(kinds[0], QuestionHtmlBlockKind.title);
    expect(kinds[2], isNot(QuestionHtmlBlockKind.title));
    expect(kinds[3], QuestionHtmlBlockKind.subQuestion);
  });
}
