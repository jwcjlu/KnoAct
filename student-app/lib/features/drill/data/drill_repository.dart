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
  });
  final int id;
  final String primary;
  final String secondary;
  final String example;
  final String source; // new | review
  final int? sourcePage;

  factory DrillItem.fromJson(Map<String, dynamic> j) => DrillItem(
        id: (j['id'] as num?)?.toInt() ?? 0,
        primary: '${j['primary'] ?? ''}',
        secondary: '${j['secondary'] ?? ''}',
        example: '${j['example'] ?? ''}',
        source: '${j['source'] ?? 'new'}',
        sourcePage: (j['source_page'] as num?)?.toInt(),
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
