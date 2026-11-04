import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/app.dart';
import 'package:student_app/core/router.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/center/speech_player.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';

const _a = Child(4, '金同学');
const _b = Child(5, '李同学');

class FlowAuthRepository implements AuthRepository {
  @override
  Future<Child> login(String name) async => name == _a.name ? _a : _b;
}

/// 按孩子 id 返回不同数据；[gates] 中有该孩子时首页请求挂起
class FlowHomeRepository implements HomeRepository {
  final gates = <int, Completer<void>>{};

  static const _names = {4: '金同学', 5: '李同学'};
  static const _points = {4: 350, 5: 120};
  static const _titles = {4: '金同学的阅读任务', 5: '李同学的听力任务'};

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) async {
    final gate = gates[userId];
    if (gate != null) await gate.future;
    return HomeSnapshot(
      userName: _names[userId]!,
      lessonProgress: const LessonProgress(current: 3, total: 8, mastered: 1, currentLessonId: 46),
    );
  }

  @override
  Future<List<StudyTask>> tasks(int userId, String date) async => [
        StudyTask(id: userId * 10, subject: '语文', taskType: 'custom', title: _titles[userId]!, detail: '', points: 20, submitStatus: 'not_started'),
      ];

  @override
  Future<int> balance(int userId, {int? bucketId}) async => _points[userId]!;

  @override
  Future<List<BucketInfo>> buckets(int userId) async => const [];

  @override
  Future<bool> redeem(int userId, String device, int minutes) async => true;

  @override
  Future<void> submitTask(int taskId) async {}
}

class FlowCenterRepository implements CenterRepository {
  @override
  Future<CenterMaterial> listening(int userId) async => CenterMaterial.empty;

  @override
  Future<CenterMaterial> reading(int userId) async => CenterMaterial.empty;

  @override
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {}
}

class SilentSpeechPlayer implements SpeechPlayer {
  @override
  Future<void> speak(String text) async {}

  @override
  Future<void> stop() async {}

  @override
  Future<void> dispose() async {}
}

Future<(ProviderContainer, FlowHomeRepository)> pumpApp(WidgetTester tester, {Map<String, Object> prefs = const {}}) async {
  SharedPreferences.setMockInitialValues(prefs);
  tester.view.physicalSize = const Size(600, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final home = FlowHomeRepository();
  final container = ProviderContainer(
    overrides: [
      authRepositoryProvider.overrideWithValue(FlowAuthRepository()),
      homeRepositoryProvider.overrideWithValue(home),
      centerRepositoryProvider.overrideWithValue(FlowCenterRepository()),
      speechPlayerProvider.overrideWithValue(SilentSpeechPlayer()),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(UncontrolledProviderScope(container: container, child: const StudentApp()));
  await tester.pumpAndSettle();
  return (container, home);
}

Future<void> login(WidgetTester tester, String name, {bool settle = true}) async {
  await tester.enterText(find.byType(TextField), name);
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
  if (settle) await tester.pumpAndSettle();
}

/// [checkErrors] 为 true 时逐帧检查退出过程中没有闪出错误提示
Future<void> logout(WidgetTester tester, {bool checkErrors = false}) async {
  await tester.tap(find.text('我的'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('退出登录'));
  for (var i = 0; i < 5; i++) {
    await tester.pump();
    if (checkErrors) {
      expect(find.text('积分加载失败'), findsNothing);
      expect(find.text('刷新失败，请稍后重试'), findsNothing);
    }
  }
  await tester.pumpAndSettle();
}

String location(ProviderContainer c) => c.read(routerProvider).routerDelegate.currentConfiguration.uri.path;

void main() {
  testWidgets('退出登录回到登录页，不提示刷新失败', (tester) async {
    await pumpApp(tester);
    await login(tester, _a.name);
    expect(find.textContaining(_a.name), findsWidgets);
    await tester.tap(find.text('我的'));
    await tester.pumpAndSettle();
    expect(find.text('350 积分'), findsOneWidget);
    await tester.tap(find.text('首页'));
    await tester.pumpAndSettle();

    await logout(tester, checkErrors: true);
    expect(find.widgetWithText(FilledButton, '开始学习'), findsOneWidget);
    expect(find.text('刷新失败，请稍后重试'), findsNothing);
    expect(find.text('积分加载失败'), findsNothing);
  });

  testWidgets('换孩子登录：加载中不显示上一个孩子的数据', (tester) async {
    final (_, home) = await pumpApp(tester);
    await login(tester, _a.name);
    expect(find.text('金同学的阅读任务'), findsOneWidget);
    await logout(tester);

    final gate = home.gates[_b.id] = Completer<void>();
    await login(tester, _b.name, settle: false);
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.textContaining(_a.name), findsNothing);
      expect(find.text('350'), findsNothing);
      expect(find.text('金同学的阅读任务'), findsNothing);
    }
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    gate.complete();
    await tester.pumpAndSettle();
    expect(find.textContaining(_b.name), findsWidgets);
    expect(find.text('120'), findsOneWidget);
    expect(find.text('李同学的听力任务'), findsOneWidget);
    expect(find.textContaining(_a.name), findsNothing);
  });

  testWidgets('未登录访问任意页面都跳到登录页', (tester) async {
    final (c, _) = await pumpApp(tester);
    expect(location(c), '/login');
    expect(find.widgetWithText(FilledButton, '开始学习'), findsOneWidget);
    for (final path in ['/home', '/center', '/profile', '/nope']) {
      c.read(routerProvider).go(path);
      await tester.pumpAndSettle();
      expect(location(c), '/login', reason: path);
    }
  });

  testWidgets('已登录访问未知路径跳到首页', (tester) async {
    final (c, _) = await pumpApp(tester, prefs: {'knoact_child_id': _a.id, 'knoact_child_name': _a.name});
    expect(location(c), '/home');
    c.read(routerProvider).go('/nope');
    await tester.pumpAndSettle();
    expect(location(c), '/home');
    expect(find.text('金同学的阅读任务'), findsOneWidget);
  });
}
