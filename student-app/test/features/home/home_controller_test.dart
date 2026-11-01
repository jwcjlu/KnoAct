import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/home/home_controller.dart';
import 'package:student_app/features/home/ui/home_page.dart';

const _lessonBySubject = {'语文': 3, '英语': 5, '数学': 2};

class ControllableHomeRepository implements HomeRepository {
  final failSubjects = <String>{};
  final gates = <String, Completer<void>>{};
  Completer<bool>? redeemGate;
  int redeemCalls = 0;

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) async {
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
  Future<int> balance(int userId) async => 350;

  @override
  Future<bool> redeem(int userId, String device, int minutes) async {
    redeemCalls++;
    return redeemGate == null ? true : redeemGate!.future;
  }

  @override
  Future<void> submitTask(int taskId) async {}
}

Future<ProviderContainer> makeContainer(ControllableHomeRepository repo) async {
  SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
  final container = ProviderContainer(
    overrides: [homeRepositoryProvider.overrideWithValue(repo)],
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
