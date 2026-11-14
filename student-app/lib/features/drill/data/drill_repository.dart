import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 专项训练的 Task.content（schema v2）解析后的会话数据。
class DrillSession {
  const DrillSession({
    required this.groupId,
    required this.kind,
    required this.steps,
    required this.intro,
    required this.groupRule,
    required this.items,
    required this.reviewItems,
    required this.quiz,
  });

  final int groupId;
  final String kind; // phrase | outline | explore
  final List<String> steps;
  final DrillIntro intro;
  final DrillRule groupRule;
  final List<DrillItem> items;
  final List<DrillItem> reviewItems;
  final List<DrillQuiz> quiz;

  factory DrillSession.fromJson(Map<String, dynamic> j) {
    final steps = (j['steps'] as List?)?.map((e) => '$e').toList() ?? const [];
    final intro = DrillIntro.fromJson(_asMap(j['intro']));
    final rule = DrillRule.fromJson(_asMap(j['group_rule']));
    final items = (j['items_snapshot'] as List?)
            ?.whereType<Map>()
            .map((e) => DrillItem.fromJson(Map<String, dynamic>.from(e)))
            .toList() ??
        const [];
    final newItems = items.where((i) => i.source != 'review').toList();
    final reviewItems = items.where((i) => i.source == 'review').toList();
    final quiz = (j['quiz'] as List?)
            ?.whereType<Map>()
            .map((e) => DrillQuiz.fromJson(Map<String, dynamic>.from(e)))
            .toList() ??
        const [];
    return DrillSession(
      groupId: (j['group_id'] as num?)?.toInt() ?? 0,
      kind: '${j['kind'] ?? ''}',
      steps: steps,
      intro: intro,
      groupRule: rule,
      items: newItems,
      reviewItems: reviewItems,
      quiz: quiz,
    );
  }
}

class DrillIntro {
  const DrillIntro({this.situation = '', this.goal = '', this.route = ''});
  final String situation;
  final String goal;
  final String route;

  factory DrillIntro.fromJson(Map<String, dynamic> j) => DrillIntro(
        situation: '${j['situation'] ?? ''}',
        goal: '${j['goal'] ?? ''}',
        route: '${j['route'] ?? ''}',
      );
  bool get isEmpty => situation.isEmpty && goal.isEmpty && route.isEmpty;
}

class DrillRule {
  const DrillRule({this.examples = const [], this.question = '', this.reveal = ''});
  final List<DrillRuleExample> examples;
  final String question;
  final String reveal;

  factory DrillRule.fromJson(Map<String, dynamic> j) => DrillRule(
        examples: (j['examples'] as List?)
                ?.whereType<Map>()
                .map((e) => DrillRuleExample.fromJson(Map<String, dynamic>.from(e)))
                .toList() ??
            const [],
        question: '${j['question'] ?? ''}',
        reveal: '${j['reveal'] ?? ''}',
      );
  bool get isEmpty => examples.isEmpty && question.isEmpty && reveal.isEmpty;
}

class DrillRuleExample {
  const DrillRuleExample({this.oe = '', this.oc = ''});
  final String oe;
  final String oc;
  factory DrillRuleExample.fromJson(Map<String, dynamic> j) =>
      DrillRuleExample(oe: '${j['oe'] ?? ''}', oc: '${j['oc'] ?? ''}');
}

class DrillItem {
  const DrillItem({
    required this.id,
    this.primary = '',
    this.secondary = '',
    this.example = '',
    this.source = 'new',
    this.sourcePage,
    this.type = 'memorize',
    this.explore = const {},
  });
  final int id;
  final String primary;
  final String secondary;
  final String example;
  final String source; // new | review
  final int? sourcePage;
  final String type; // memorize | explore
  final Map<String, dynamic> explore; // 探究内容（compare/classify/formula/trap）

  factory DrillItem.fromJson(Map<String, dynamic> j) => DrillItem(
        id: (j['id'] as num?)?.toInt() ?? 0,
        primary: '${j['primary'] ?? ''}',
        secondary: '${j['secondary'] ?? ''}',
        example: '${j['example'] ?? ''}',
        source: '${j['source'] ?? 'new'}',
        sourcePage: (j['source_page'] as num?)?.toInt(),
        type: '${j['type'] ?? 'memorize'}',
        explore: j['explore'] is Map ? Map<String, dynamic>.from(j['explore'] as Map) : const {},
      );

  /// explore 的 guide 链（递进引导步骤）。
  List<GuideStep> get guideSteps {
    final g = explore['guide'];
    if (g is! List) return const [];
    return [for (final e in g.whereType<Map>()) GuideStep.fromJson(Map<String, dynamic>.from(e))];
  }
}

/// guide 链的一轮：选择题（前 N-1 轮）或填空题（最后一轮归纳）。
class GuideStep {
  const GuideStep({
    this.prompt = '',
    this.samples = const [],
    this.options = const [],
    this.answerIndex = -1,
    this.answer = '',
    this.reveal = '',
  });

  final String prompt;
  final List<String> samples;
  final List<String> options;
  final int answerIndex; // -1 = 填空轮
  final String answer;   // 填空轮答案
  final String reveal;

  bool get isChoice => options.isNotEmpty && answerIndex >= 0;

  factory GuideStep.fromJson(Map<String, dynamic> j) => GuideStep(
        prompt: '${j['prompt'] ?? ''}',
        samples: j['samples'] is List ? (j['samples'] as List).map((e) => '$e').toList() : const [],
        options: j['options'] is List ? (j['options'] as List).map((e) => '$e').toList() : const [],
        answerIndex: (j['answer_index'] as num?)?.toInt() ?? -1,
        answer: '${j['answer'] ?? ''}',
        reveal: '${j['reveal'] ?? ''}',
      );
}

class DrillQuiz {
  const DrillQuiz({
    required this.itemId,
    this.qtype = 'blank',
    this.prompt = '',
    this.answer = '',
    this.explain = '',
    this.source = 'new',
  });
  final int itemId;
  final String qtype; // blank | spot_error
  final String prompt;
  final String answer;
  final String explain;
  final String source;

  factory DrillQuiz.fromJson(Map<String, dynamic> j) => DrillQuiz(
        itemId: (j['item_id'] as num?)?.toInt() ?? 0,
        qtype: '${j['qtype'] ?? 'blank'}',
        prompt: '${j['prompt'] ?? ''}',
        answer: '${j['answer'] ?? ''}',
        explain: '${j['explain'] ?? ''}',
        source: '${j['source'] ?? 'new'}',
      );
}

Map<String, dynamic> _asMap(Object? v) =>
    v is Map ? Map<String, dynamic>.from(v) : const {};

/// 解析 Task.content JSON 字符串为 DrillSession；非法/空返回 null。
DrillSession? parseDrillContent(String content) {
  if (content.isEmpty) return null;
  try {
    final d = jsonDecode(content);
    if (d is! Map) return null;
    return DrillSession.fromJson(Map<String, dynamic>.from(d));
  } catch (_) {
    return null;
  }
}

/// 执行计划的一步：step 名 + 绑定的条目（null = 组级规律卡）。
class PlanStep {
  const PlanStep(this.step, this.itemId);
  final String step;
  final int? itemId;
}

/// 按条目类型生成执行序列：先识记段（认→每条目用+测），后探究段（观察→每条目归类/归纳/陷阱）。
List<PlanStep> buildPlan(DrillSession session) {
  final plan = <PlanStep>[];
  final memorize = session.items.where((it) => it.type != 'explore').toList();
  final explore = session.items.where((it) => it.type == 'explore').toList();

  if (memorize.isNotEmpty) {
    plan.add(const PlanStep('recognize', null));
    for (final item in memorize) {
      plan.add(PlanStep('produce', item.id));
      plan.add(PlanStep('quiz', item.id));
    }
  }

  if (explore.isNotEmpty) {
    plan.add(const PlanStep('observe', null));
    for (final item in explore) {
      plan.add(PlanStep('classify', item.id));
      plan.add(PlanStep('formula', item.id));
      plan.add(PlanStep('trap', item.id));
    }
  }

  // 兜底：没有任何条目时，退回旧组级 steps
  if (plan.isEmpty && session.items.isEmpty && session.steps.isNotEmpty) {
    for (final s in session.steps) {
      plan.add(PlanStep(s, null));
    }
  }
  return plan;
}

class DrillRepository {
  DrillRepository(this._api);
  final ApiClient _api;

  Future<Map<String, dynamic>> step({
    required int taskId,
    required String step,
    required int itemId,
    required String answer,
    required bool requestHint,
  }) async {
    final d = await _api.post('/api/tasks/$taskId/drill-step', body: {
      'step': step,
      'item_id': itemId,
      'answer': answer,
      'request_hint': requestHint,
    });
    return asMap(d);
  }

  Future<Map<String, dynamic>> sentence({
    required int taskId,
    required int itemId,
    required String sentence,
  }) async {
    final d = await _api.post('/api/tasks/$taskId/drill-sentence', body: {
      'item_id': itemId,
      'sentence': sentence,
    });
    return asMap(d);
  }

  Future<Map<String, dynamic>> apply({
    required int taskId,
    required int itemId,
    required String sentence,
  }) async {
    final d = await _api.post('/api/tasks/$taskId/drill-apply', body: {
      'item_id': itemId,
      'sentence': sentence,
    });
    return asMap(d);
  }

  Future<Map<String, dynamic>> complete({
    required int taskId,
    required Map<String, bool> results,
  }) async {
    final d = await _api.post('/api/tasks/$taskId/drill-complete', body: {
      'results': results,
    });
    return asMap(d);
  }
}

final drillRepositoryProvider =
    Provider<DrillRepository>((ref) => DrillRepository(ref.watch(apiClientProvider)));
