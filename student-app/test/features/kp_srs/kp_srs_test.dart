import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/kp_srs/data/kp_srs_repository.dart';
import 'package:student_app/features/kp_srs/kp_srs_controller.dart';
import 'package:student_app/features/kp_srs/ui/kp_srs_page.dart';

import '../auth/session_test.dart' show FakeAuthRepository;
import '../home/home_controller_test.dart' show ControllableHomeRepository;

class FakeApi implements ApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);

  final calls = <String>[];
  final posts = <Map<String, dynamic>>[];
  Object? getResult = {'items': <Object>[]};
  Object? postResult = {'ok': true, 'result': 'remember', 'graded': false};
  bool failPost = false;

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    calls.add('GET $path $query');
    return getResult;
  }

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    calls.add('POST $path');
    if (failPost) throw ApiException('boom');
    posts.add(Map<String, dynamic>.from(body as Map));
    return postResult;
  }
}

Map<String, dynamic> _selfRateItem(int id, String title) => {
      'item_id': id,
      'knowledge_point_id': id + 100,
      'title': title,
      'content': '$title 的完整内容',
      'lesson_title': '第一课',
      'prompt': {'source': 'self_rate', 'question_id': null, 'question': null, 'qtype': null},
    };

Map<String, dynamic> _questionItem(int id, String title, int qid, String q) => {
      'item_id': id,
      'knowledge_point_id': id + 100,
      'title': title,
      'content': '$title 的完整内容',
      'lesson_title': '第一课',
      'prompt': {'source': 'generated', 'question_id': qid, 'question': q, 'qtype': 'short'},
    };

Future<ProviderContainer> _container(FakeApi api) async {
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  final c = ProviderContainer(
    overrides: [
      kpSrsRepositoryProvider.overrideWithValue(KpSrsRepository(api)),
      homeRepositoryProvider.overrideWithValue(ControllableHomeRepository()),
      authRepositoryProvider.overrideWithValue(FakeAuthRepository(const Child(4, '金同学'))),
    ],
    retry: (_, _) => null,
  );
  addTearDown(c.dispose);
  await c.read(sessionProvider.future);
  c.listen(kpSrsControllerProvider, (_, _) {});
  return c;
}

Future<void> _pumpPage(WidgetTester tester, ProviderContainer c) async {
  tester.view.physicalSize = const Size(420, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = GoRouter(
    initialLocation: '/kp-srs',
    routes: [
      GoRoute(path: '/kp-srs', builder: (_, _) => const KpSrsPage()),
      GoRoute(path: '/home', builder: (_, _) => const Scaffold(body: Text('home'))),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(UncontrolledProviderScope(container: c, child: MaterialApp.router(routerConfig: router)));
  await tester.pumpAndSettle();
}

void main() {
  group('解析与 repository', () {
    test('解析 kp_review 任务 content 快照', () {
      final items = parseKpSrsContent(jsonEncode([
        _selfRateItem(1, '比喻'),
        _questionItem(2, '拟人', 77, '什么是拟人？'),
      ]));
      expect(items.length, 2);
      expect(items[0].itemId, 1);
      expect(items[0].knowledgePointId, 101);
      expect(items[0].lessonTitle, '第一课');
      expect(items[0].prompt.hasQuestion, isFalse);
      expect(items[0].prompt.source, 'self_rate');
      expect(items[1].prompt.hasQuestion, isTrue);
      expect(items[1].prompt.questionId, 77);
      expect(items[1].prompt.question, '什么是拟人？');
    });

    test('空串 / 非 JSON / 非数组 / 无 item_id 都得到空列表', () {
      expect(parseKpSrsContent(''), isEmpty);
      expect(parseKpSrsContent('not json'), isEmpty);
      expect(parseKpSrsContent('{"a":1}'), isEmpty);
      expect(parseKpSrsContent('[{"title":"x"}]'), isEmpty);
    });

    test('prompt 有 question_id 无题干时退化为自评', () {
      final p = KpSrsPrompt.fromJson({'source': 'reuse', 'question_id': 5, 'question': ''});
      expect(p.hasQuestion, isFalse);
      expect(p.questionId, isNull);
    });

    test('fetchDue 带 user_id 并解析 items', () async {
      final api = FakeApi()..getResult = {'items': [_selfRateItem(1, '比喻')]};
      final items = await KpSrsRepository(api).fetchDue(userId: 4);
      expect(items.single.itemId, 1);
      expect(api.calls.single, 'GET /api/knowledge-review/due {user_id: 4}');
    });

    test('complete 发送 body 并解析判分响应', () async {
      final api = FakeApi()
        ..postResult = {
          'ok': true,
          'result': 'forgot',
          'is_correct': false,
          'graded': true,
          'interval_index': 0,
          'next_review_at': '2026-11-28T00:00:00',
        };
      final r = await KpSrsRepository(api).complete(
        userId: 4,
        itemId: 9,
        result: kpResultRemember,
        questionId: 77,
        studentAnswer: '答案',
        durationMs: 1200,
      );
      expect(api.calls.single, 'POST /api/knowledge-review/complete');
      expect(api.posts.single, {
        'user_id': 4,
        'item_id': 9,
        'result': 'remember',
        'question_id': 77,
        'student_answer': '答案',
        'duration_ms': 1200,
      });
      expect(r.result, 'forgot');
      expect(r.isCorrect, isFalse);
      expect(r.graded, isTrue);
    });

    test('complete 自评不带 question_id / student_answer', () async {
      final api = FakeApi();
      await KpSrsRepository(api).complete(userId: 4, itemId: 9, result: kpResultFuzzy);
      expect(api.posts.single.containsKey('question_id'), isFalse);
      expect(api.posts.single.containsKey('student_answer'), isFalse);
    });
  });

  group('controller', () {
    test('任务入口：有快照时直接用快照，不请求 due', () async {
      final api = FakeApi();
      final c = await _container(api);
      await c
          .read(kpSrsControllerProvider.notifier)
          .init(taskId: 8, content: jsonEncode([_selfRateItem(1, '比喻')]), title: '知识点复习');
      final s = c.read(kpSrsControllerProvider);
      expect(s.items.length, 1);
      expect(s.taskId, 8);
      expect(api.calls, isEmpty);
    });

    test('独立入口：taskId 为空时加载 due', () async {
      final api = FakeApi()..getResult = {'items': [_selfRateItem(1, '比喻'), _selfRateItem(2, '拟人')]};
      final c = await _container(api);
      await c.read(kpSrsControllerProvider.notifier).init(taskId: null);
      final s = c.read(kpSrsControllerProvider);
      expect(s.items.length, 2);
      expect(s.taskId, isNull);
      expect(s.loading, isFalse);
      expect(api.calls.single, startsWith('GET /api/knowledge-review/due'));
    });

    test('独立入口无到期项 → 空状态', () async {
      final c = await _container(FakeApi());
      await c.read(kpSrsControllerProvider.notifier).init(taskId: null);
      final s = c.read(kpSrsControllerProvider);
      expect(s.isEmpty, isTrue);
      expect(s.isDone, isFalse);
    });

    test('自评：记得直接进入下一项；忘了停下展开内容再继续；全部做完 isDone', () async {
      final api = FakeApi();
      final c = await _container(api);
      final ctl = c.read(kpSrsControllerProvider.notifier);
      await ctl.init(taskId: 8, content: jsonEncode([_selfRateItem(1, '比喻'), _selfRateItem(2, '拟人')]));

      await ctl.selfRate(kpResultRemember);
      var s = c.read(kpSrsControllerProvider);
      expect(s.index, 1);
      expect(s.completed, 1);
      expect(s.feedback, isNull);
      expect(api.posts.single['item_id'], 1);
      expect(api.posts.single['result'], 'remember');
      expect(api.posts.single.containsKey('question_id'), isFalse);

      api.postResult = {'ok': true, 'result': 'forgot', 'graded': false};
      await ctl.selfRate(kpResultForgot);
      s = c.read(kpSrsControllerProvider);
      expect(s.index, 1, reason: '忘了：停在本项展示原文');
      expect(s.revealContent, isTrue);
      expect(s.completed, 2);

      ctl.next();
      s = c.read(kpSrsControllerProvider);
      expect(s.isDone, isTrue);
      expect(s.completed, 2);
    });

    test('带题：提交答案以服务端判分结果为准（答错 → forgot，展开内容）', () async {
      final api = FakeApi()..postResult = {'ok': true, 'result': 'forgot', 'is_correct': false, 'graded': true};
      final c = await _container(api);
      final ctl = c.read(kpSrsControllerProvider.notifier);
      await ctl.init(taskId: 8, content: jsonEncode([_questionItem(3, '对偶', 55, '什么是对偶？')]));

      await ctl.submitAnswer();
      expect(api.posts, isEmpty, reason: '空答案不提交');

      ctl.setAnswer('  乱答  ');
      await ctl.submitAnswer();
      expect(api.posts.single['question_id'], 55);
      expect(api.posts.single['student_answer'], '乱答');
      final s = c.read(kpSrsControllerProvider);
      expect(s.feedback?.graded, isTrue);
      expect(s.feedback?.isCorrect, isFalse);
      expect(s.revealContent, isTrue);
    });

    test('提交失败不推进，保留可重试，不计数', () async {
      final api = FakeApi()..failPost = true;
      final c = await _container(api);
      final ctl = c.read(kpSrsControllerProvider.notifier);
      await ctl.init(taskId: 8, content: jsonEncode([_selfRateItem(1, '比喻')]));
      await ctl.selfRate(kpResultRemember);
      var s = c.read(kpSrsControllerProvider);
      expect(s.index, 0);
      expect(s.completed, 0);
      expect(s.busy, isFalse);
      expect(s.error, isNotNull);

      api.failPost = false;
      await ctl.selfRate(kpResultRemember);
      s = c.read(kpSrsControllerProvider);
      expect(s.isDone, isTrue);
      expect(s.completed, 1);
    });

    test('有点忘：不展开原文，直接进入下一项', () async {
      final api = FakeApi()..postResult = {'ok': true, 'result': 'fuzzy', 'graded': false};
      final c = await _container(api);
      final ctl = c.read(kpSrsControllerProvider.notifier);
      await ctl.init(
        taskId: 8,
        content: jsonEncode([_selfRateItem(1, '比喻'), _selfRateItem(2, '拟人')]),
      );
      await ctl.selfRate(kpResultFuzzy);
      final s = c.read(kpSrsControllerProvider);
      expect(api.posts.single['result'], 'fuzzy');
      expect(s.index, 1);
      expect(s.completed, 1);
      expect(s.revealContent, isFalse);
      expect(s.feedback, isNull);
    });

    test('complete 解析 already_completed 与 interval 字段', () {
      final r = KpSrsCompleteResult.fromJson({
        'ok': true,
        'result': 'remember',
        'graded': false,
        'already_completed': true,
        'interval_index': 2,
        'next_review_at': '2026-12-01T00:00:00',
      });
      expect(r.alreadyCompleted, isTrue);
      expect(r.intervalIndex, 2);
      expect(r.nextReviewAt, '2026-12-01T00:00:00');
    });
  });

  group('page', () {
    testWidgets('空状态：今天没有要复习的知识点', (tester) async {
      final c = await _container(FakeApi());
      await c.read(kpSrsControllerProvider.notifier).init(taskId: null);
      await _pumpPage(tester, c);
      expect(find.text('今天没有要复习的知识点'), findsOneWidget);
    });

    testWidgets('未经入口直接进入页面：自动按独立入口加载', (tester) async {
      final api = FakeApi()..getResult = {'items': [_selfRateItem(1, '比喻')]};
      final c = await _container(api);
      await _pumpPage(tester, c);
      expect(api.calls.single, startsWith('GET /api/knowledge-review/due'));
      expect(find.byKey(const ValueKey('kp-srs-remember')), findsOneWidget);
    });

    testWidgets('自评三按钮；忘了展开内容；完成页只说「按计划复习了 N 个」，不说已掌握', (tester) async {
      final api = FakeApi();
      final c = await _container(api);
      await c
          .read(kpSrsControllerProvider.notifier)
          .init(taskId: 8, content: jsonEncode([_selfRateItem(1, '比喻'), _selfRateItem(2, '拟人')]));
      await _pumpPage(tester, c);

      expect(find.text('记得'), findsOneWidget);
      expect(find.text('有点忘'), findsOneWidget);
      expect(find.text('忘了'), findsOneWidget);
      expect(find.byKey(const ValueKey('kp-srs-content')), findsNothing);

      api.postResult = {'ok': true, 'result': 'forgot', 'graded': false};
      await tester.tap(find.byKey(const ValueKey('kp-srs-forgot')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('kp-srs-content')), findsOneWidget);
      expect(find.text('比喻 的完整内容'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('kp-srs-next')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('kp-srs-content')), findsNothing);

      api.postResult = {'ok': true, 'result': 'remember', 'graded': false};
      await tester.tap(find.byKey(const ValueKey('kp-srs-remember')));
      await tester.pumpAndSettle();

      expect(find.text('今天按计划复习了 2 个知识点'), findsOneWidget);
      expect(find.textContaining('已掌握'), findsNothing);
    });

    testWidgets('有点忘：不展开内容，自动切到下一项', (tester) async {
      final api = FakeApi()..postResult = {'ok': true, 'result': 'fuzzy', 'graded': false};
      final c = await _container(api);
      await c
          .read(kpSrsControllerProvider.notifier)
          .init(taskId: 8, content: jsonEncode([_selfRateItem(1, '比喻'), _selfRateItem(2, '拟人')]));
      await _pumpPage(tester, c);

      await tester.tap(find.byKey(const ValueKey('kp-srs-fuzzy')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('kp-srs-content')), findsNothing);
      expect(find.text('拟人'), findsWidgets);
      expect(find.byKey(const ValueKey('kp-srs-remember')), findsOneWidget);
    });

    testWidgets('带题：输入答案并提交，答错展示反馈与原文', (tester) async {
      final api = FakeApi()..postResult = {'ok': true, 'result': 'forgot', 'is_correct': false, 'graded': true};
      final c = await _container(api);
      await c
          .read(kpSrsControllerProvider.notifier)
          .init(taskId: 8, content: jsonEncode([_questionItem(3, '对偶', 55, '什么是对偶？')]));
      await _pumpPage(tester, c);

      expect(find.text('什么是对偶？'), findsOneWidget);
      expect(find.byKey(const ValueKey('kp-srs-remember')), findsNothing);
      final submit = find.byKey(const ValueKey('kp-srs-submit'));
      expect(tester.widget<FilledButton>(submit).onPressed, isNull);

      await tester.enterText(find.byKey(const ValueKey('kp-srs-answer-0')), '字数相等');
      await tester.pump();
      await tester.tap(submit);
      await tester.pumpAndSettle();

      expect(api.posts.single['question_id'], 55);
      expect(find.byKey(const ValueKey('kp-srs-feedback')), findsOneWidget);
      expect(find.byKey(const ValueKey('kp-srs-content')), findsOneWidget);
      expect(find.textContaining('已掌握'), findsNothing);
    });
  });
}
