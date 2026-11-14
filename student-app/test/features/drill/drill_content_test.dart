import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/drill/data/drill_repository.dart';

void main() {
  group('parseDrillContent', () {
    test('解析 schema v2 的 phrase 内容', () {
      const content = '''
      {
        "schema_version": 2,
        "group_id": 10,
        "kind": "phrase",
        "steps": ["recognize", "recall", "produce", "quiz"],
        "intro": {"situation": "今天攻克 look 短语", "goal": "能认能背能用", "route": "4 关"},
        "group_rule": {
          "examples": [{"oe": "look after", "oc": "照顾"}],
          "question": "有什么共同点？",
          "reveal": "look + 介词"
        },
        "items_snapshot": [
          {"id": 101, "primary": "look after", "secondary": "照顾", "source": "new"},
          {"id": 55, "primary": "give up", "secondary": "放弃", "source": "review"}
        ],
        "quiz": [
          {"item_id": 101, "qtype": "blank", "prompt": "She ___ her brother.", "answer": "looks after"},
          {"item_id": 76, "qtype": "spot_error", "prompt": "was made from 哪里错？", "answer": "was made of", "explain": "物理变化用 of"}
        ]
      }
      ''';

      final s = parseDrillContent(content);
      expect(s, isNotNull);
      expect(s!.kind, 'phrase');
      expect(s.steps, ['recognize', 'recall', 'produce', 'quiz']);
      expect(s.intro.situation, '今天攻克 look 短语');
      expect(s.groupRule.examples, hasLength(1));
      expect(s.items, hasLength(1)); // 只含 new，review 被拆到 reviewItems
      expect(s.reviewItems, hasLength(1));
      expect(s.quiz, hasLength(2));
      expect(s.quiz[1].qtype, 'spot_error');
    });

    test('空内容返回 null', () {
      expect(parseDrillContent(''), isNull);
    });

    test('非法 JSON 返回 null', () {
      expect(parseDrillContent('not json'), isNull);
    });

    test('explore kind 解析 steps', () {
      const content = '''
      {"kind": "explore", "steps": ["observe", "classify", "formula", "trap"], "items_snapshot": []}
      ''';
      final s = parseDrillContent(content);
      expect(s!.steps, ['observe', 'classify', 'formula', 'trap']);
    });
  });

  group('buildPlan', () {
    DrillSession makeSession(List<Map<String, dynamic>> items) {
      return DrillSession(
        groupId: 1,
        kind: 'explore',
        steps: const ['observe', 'classify', 'formula', 'trap'],
        intro: const DrillIntro(),
        groupRule: const DrillRule(),
        items: items.map((e) => DrillItem.fromJson(e)).toList(),
        reviewItems: const [],
        quiz: const [],
      );
    }

    test('识记条目走 认→用→测，探究条目走 观察→归类→归纳→陷阱', () {
      final s = makeSession([
        {'id': 1, 'primary': '古诗', 'type': 'memorize'},
        {'id': 2, 'primary': '比喻', 'type': 'explore'},
      ]);
      final plan = buildPlan(s);
      final steps = plan.map((p) => p.step).toList();
      expect(steps, ['recognize', 'produce', 'quiz', 'observe', 'classify', 'formula', 'trap']);
      expect(plan[0].itemId, isNull); // recognize 组级
      expect(plan[1].itemId, 1);       // produce 绑定条目1
      expect(plan[4].itemId, 2);       // classify 绑定条目2
    });

    test('纯识记组：无探究段', () {
      final s = makeSession([
        {'id': 1, 'primary': 'a', 'type': 'memorize'},
        {'id': 2, 'primary': 'b', 'type': 'memorize'},
      ]);
      final plan = buildPlan(s);
      expect(plan.map((p) => p.step).toList(),
          ['recognize', 'produce', 'quiz', 'produce', 'quiz']);
    });

    test('纯探究组：无识记段', () {
      final s = makeSession([
        {'id': 1, 'primary': '周长', 'type': 'explore'},
      ]);
      final plan = buildPlan(s);
      expect(plan.map((p) => p.step).toList(),
          ['observe', 'classify', 'formula', 'trap']);
    });
  });
}