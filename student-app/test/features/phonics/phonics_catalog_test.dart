import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/phonics/data/phonics_catalog.dart';

const _fixture = '''
{
  "version": 1,
  "stages": [
    {"id": 1, "name": "阶段一", "path_order_min": 1, "path_order_max": 10},
    {"id": 2, "name": "阶段二", "path_order_min": 11, "path_order_max": 20}
  ],
  "rules": [
    {
      "id": "vowel.a.short",
      "category": "vowel",
      "grapheme": "a",
      "ipa": "/æ/",
      "approx_zh": "近似「埃」短音",
      "path_order": 5,
      "notes": "",
      "rule_audio": "phonics/audio/rule/vowel.a.short.wav",
      "example_words": [
        {"word": "cat", "grades": [3, 5], "audio": "phonics/audio/word/cat.wav"}
      ]
    },
    {
      "id": "vowel_team.ai.primary",
      "category": "vowel_team",
      "grapheme": "ai",
      "ipa": "/eɪ/",
      "approx_zh": "近似「诶」",
      "path_order": 15,
      "notes": "",
      "rule_audio": "phonics/audio/rule/vowel_team.ai.primary.wav",
      "example_words": []
    },
    {
      "id": "orphan.rule",
      "category": "vowel",
      "grapheme": "zz",
      "ipa": "/z/",
      "approx_zh": "",
      "path_order": 999,
      "notes": "",
      "rule_audio": "phonics/audio/rule/orphan.wav",
      "example_words": []
    }
  ]
}
''';

void main() {
  late PhonicsCatalog catalog;

  setUp(() {
    catalog = PhonicsCatalog.parse(_fixture);
  });

  test('parses stages and rules', () {
    expect(catalog.version, 1);
    expect(catalog.stages, hasLength(2));
    expect(catalog.rules, hasLength(3));
    expect(catalog.rules.first.grapheme, 'a');
    expect(catalog.rules.first.ruleAudio, 'phonics/audio/rule/vowel.a.short.wav');
  });

  test('rulesInStage filters by path_order inclusive', () {
    final s1 = catalog.stages.first;
    final in1 = catalog.rulesInStage(s1);
    expect(in1.map((r) => r.id), ['vowel.a.short']);
    final in2 = catalog.rulesInStage(catalog.stages[1]);
    expect(in2.map((r) => r.id), ['vowel_team.ai.primary']);
  });

  test('rulesInStage sorted by path_order', () {
    final raw = PhonicsCatalog.parse('''
{
  "version": 1,
  "stages": [{"id": 1, "name": "s", "path_order_min": 1, "path_order_max": 10}],
  "rules": [
    {"id": "b", "category": "vowel", "grapheme": "b", "ipa": "", "approx_zh": "",
     "path_order": 8, "notes": "", "rule_audio": "x", "example_words": []},
    {"id": "a", "category": "vowel", "grapheme": "a", "ipa": "", "approx_zh": "",
     "path_order": 2, "notes": "", "rule_audio": "x", "example_words": []}
  ]
}
''');
    expect(raw.rulesInStage(raw.stages.first).map((r) => r.id), ['a', 'b']);
  });

  test('findRule by id', () {
    expect(catalog.findRule('vowel.a.short')?.grapheme, 'a');
    expect(catalog.findRule('missing'), isNull);
  });
}
