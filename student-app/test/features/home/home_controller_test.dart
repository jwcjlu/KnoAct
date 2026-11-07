import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';

import '../auth/session_test.dart' show FakeAuthRepository;
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/home/home_controller.dart';
import 'package:student_app/features/home/ui/home_page.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';

const _lessonBySubject = {'语文': 3, '英语': 5, '数学': 2};

class ControllableHomeRepository implements HomeRepository {
  final failSubjects = <String>{};
  final gates = <String, Completer<void>>{};
  Completer<bool>? redeemGate;
  int redeemCalls = 0;
  int snapshotCalls = 0;
  int balanceCalls = 0;
  List<BucketInfo> bucketList = const [];

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) async {
    snapshotCalls++;
    final gate = gates[subject];
    if (gate != null) await gate.future;
    if (failSubjects.contains(subject)) throw ApiException('boom');
    return HomeSnapshot(
      userName: '金同学',
      lessonProgress: LessonProgress(current: _lessonBySubject[subject]!, total: 8, mastered: 1, currentLessonId: 46),
    );
  }

  @override
  Future<List<StudyTask>> tasks(int userId, String date) async => const [
        StudyTask(id: 2, subject: '语文', taskType: 'reading', title: '桂花雨 阅读理解', detail: '', points: 20, submitStatus: 'not_started'),
      ];

  @override
  Future<int> balance(int userId, {int? bucketId}) async {
    balanceCalls++;
    return 350;
  }

  @override
  Future<List<BucketInfo>> buckets(int userId) async => bucketList;

  @override
  Future<bool> redeem(int userId, String device, int minutes) async {
    redeemCalls++;
    return redeemGate == null ? true : redeemGate!.future;
  }

  @override
  Future<void> submitTask(int taskId) async {}

  @override
  Future<void> uploadTaskPhoto(int taskId, List<int> bytes, {String filename = 'dictation.jpg'}) async {}
}

Future<ProviderContainer> makeContainer(ControllableHomeRepository repo) async {
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  final container = ProviderContainer(
    overrides: [
      homeRepositoryProvider.overrideWithValue(repo),
      authRepositoryProvider.overrideWithValue(FakeAuthRepository(const Child(4, '金同学'))),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  container.listen(homeControllerProvider, (_, _) {});
  await container.read(homeControllerProvider.future);
  return container;
}

Future<ProviderContainer> pumpHome(WidgetTester tester, ControllableHomeRepository repo) async {
  tester.view.physicalSize = const Size(420, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final container = await makeContainer(repo);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: Scaffold(body: HomePage())),
  ));
  await tester.pumpAndSettle();
  return container;
}

void main() {
  testWidgets('已有数据时刷新失败：提示且保留旧内容', (tester) async {
    final repo = ControllableHomeRepository();
    final container = await pumpHome(tester, repo);
    repo.failSubjects.add('语文');
    await container.read(homeControllerProvider.notifier).reload();
    await tester.pumpAndSettle();
    expect(find.text('刷新失败，请稍后重试'), findsOneWidget);
    expect(find.textContaining('第 3 课重点学习与旧课复习'), findsOneWidget);
  });

  test('学科切换失败后，再次点同一学科可重试成功', () async {
    final repo = ControllableHomeRepository();
    final container = await makeContainer(repo);
    final notifier = container.read(homeControllerProvider.notifier);
    repo.failSubjects.add('数学');
    await notifier.setSubject('数学');
    var state = container.read(homeControllerProvider);
    expect(state.hasError, isTrue);
    expect(state.value?.subject, '语文');

    repo.failSubjects.clear();
    await notifier.setSubject('数学');
    state = container.read(homeControllerProvider);
    expect(state.hasError, isFalse);
    expect(state.value?.subject, '数学');
    expect(state.value?.snapshot.lessonProgress.current, 2);
  });

  test('快速切换学科：慢的数学结果被丢弃，最终为英语', () async {
    final repo = ControllableHomeRepository();
    final container = await makeContainer(repo);
    final notifier = container.read(homeControllerProvider.notifier);
    final mathGate = repo.gates['数学'] = Completer<void>();
    final slowMath = notifier.setSubject('数学');
    await notifier.setSubject('英语');
    mathGate.complete();
    await slowMath;
    final state = container.read(homeControllerProvider);
    expect(state.value?.subject, '英语');
    expect(state.value?.snapshot.lessonProgress.current, 5);
  });

  test('切换数学请求中点回语文：最终显示语文', () async {
    final repo = ControllableHomeRepository();
    final container = await makeContainer(repo);
    final notifier = container.read(homeControllerProvider.notifier);
    final mathGate = repo.gates['数学'] = Completer<void>();
    final slowMath = notifier.setSubject('数学');
    await notifier.setSubject('语文');
    mathGate.complete();
    await slowMath;
    final state = container.read(homeControllerProvider);
    expect(state.value?.subject, '语文');
    expect(state.value?.snapshot.lessonProgress.current, 3);
  });

  test('未登录时首页与积分保持加载，不请求也不报错', () async {
    SharedPreferences.setMockInitialValues({});
    final repo = ControllableHomeRepository();
    final c = ProviderContainer(overrides: [homeRepositoryProvider.overrideWithValue(repo)], retry: (_, _) => null);
    addTearDown(c.dispose);
    await c.read(sessionProvider.future);
    c.listen(homeControllerProvider, (_, _) {});
    c.listen(pointsProvider, (_, _) {});
    await c.read(homeControllerProvider.notifier).reload();
    await pumpEventQueue();
    final home = c.read(homeControllerProvider);
    final points = c.read(pointsProvider);
    expect(home.isLoading, isTrue);
    expect(home.hasError, isFalse);
    expect(points.isLoading, isTrue);
    expect(points.hasError, isFalse);
    expect(repo.snapshotCalls, 0);
    expect(repo.balanceCalls, 0);
  });

  test('退出登录后首页与积分不报错', () async {
    final repo = ControllableHomeRepository();
    final c = await makeContainer(repo);
    c.listen(pointsProvider, (_, _) {});
    await c.read(pointsProvider.future);
    await c.read(sessionProvider.notifier).logout();
    await pumpEventQueue();
    expect(c.read(homeControllerProvider).hasError, isFalse);
    expect(c.read(pointsProvider).hasError, isFalse);
  });

  testWidgets('兑换进行中重复点击只发一次请求', (tester) async {
    final repo = ControllableHomeRepository();
    await pumpHome(tester, repo);
    final gate = repo.redeemGate = Completer<bool>();
    final btn = find.byKey(const ValueKey('redeem-tablet'));
    await tester.scrollUntilVisible(btn, 300);
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pump();
    await tester.tap(btn);
    await tester.pump();
    gate.complete(true);
    await tester.pumpAndSettle();
    expect(repo.redeemCalls, 1);
  });
}
