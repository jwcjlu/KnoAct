import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/app.dart';
import 'package:student_app/core/router.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/center/speech_player.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';

const _a = Child(4, '金同学');
const _b = Child(5, '李同学');

class FlowAuthRepository implements AuthRepository {
  /// 在此集合里的登录名登录后 parent_bound=false
  final unbound = <String>{};
  Child? meResult;
  Child? _lastLoggedChild;

  @override
  Future<AuthSession> login(String loginName, String password) async {
    final c = loginName == _a.name ? _a : _b;
    final child = unbound.contains(loginName) ? c.copyWith(parentBound: false) : c;
    _lastLoggedChild = child;
    return AuthSession(child, accessToken: 'tok', refreshToken: 'ref');
  }

  @override
  Future<Child> me() async => meResult ?? _lastLoggedChild ?? _a;

  @override
  Future<void> bindByCode(String code) async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
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

Future<(ProviderContainer, FlowHomeRepository)> pumpApp(WidgetTester tester, {Map<String, Object> prefs = const {}, FlowAuthRepository? auth}) async {
  SharedPreferences.setMockInitialValues(prefs);
  tester.view.physicalSize = const Size(600, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final home = FlowHomeRepository();
  final container = ProviderContainer(
    overrides: [
      authRepositoryProvider.overrideWithValue(auth ?? FlowAuthRepository()),
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
  await tester.enterText(find.byKey(const Key('loginName')), name);
  await tester.enterText(find.byKey(const Key('password')), 'pw123456');
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, '登录'));
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
    expect(find.widgetWithText(FilledButton, '登录'), findsOneWidget);
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
    expect(find.widgetWithText(FilledButton, '登录'), findsOneWidget);
    for (final path in ['/home', '/center', '/profile', '/bind-parent', '/nope']) {
      c.read(routerProvider).go(path);
      await tester.pumpAndSettle();
      expect(location(c), '/login', reason: path);
    }
  });

  testWidgets('未登录可打开注册页', (tester) async {
    final (c, _) = await pumpApp(tester);
    c.read(routerProvider).go('/register');
    await tester.pumpAndSettle();
    expect(location(c), '/register');
    expect(find.text('注册账号'), findsOneWidget);
  });

  testWidgets('未绑定家长：登录后进入绑定页，其他页面都被拦回；绑定后进主界面', (tester) async {
    final auth = FlowAuthRepository()..unbound.add(_a.name);
    final (c, _) = await pumpApp(tester, auth: auth);
    await login(tester, _a.name);
    expect(location(c), '/bind-parent');
    expect(find.text('绑定家长'), findsWidgets);
    for (final path in ['/home', '/profile', '/login', '/register']) {
      c.read(routerProvider).go(path);
      await tester.pumpAndSettle();
      expect(location(c), '/bind-parent', reason: path);
    }

    auth.meResult = _a; // 绑定后 /me 返回 parent_bound=true
    await tester.enterText(find.byKey(const Key('inviteCode')), 'ABCD2345');
    await tester.pump();
    await tester.tap(find.text('用邀请码绑定'));
    await tester.pumpAndSettle();
    expect(location(c), '/home');
    expect(find.text('金同学的阅读任务'), findsOneWidget);
  });

  testWidgets('已登录访问登录/注册/绑定页回到首页', (tester) async {
    final (c, _) = await pumpApp(tester, prefs: {
      'knoact_child_id': _a.id,
      'knoact_child_name': _a.name,
      SessionStore.accessTokenKey: 'tok',
      SessionStore.refreshTokenKey: 'ref',
    });
    for (final path in ['/login', '/register', '/bind-parent']) {
      c.read(routerProvider).go(path);
      await tester.pumpAndSettle();
      expect(location(c), '/home', reason: path);
    }
  });

  testWidgets('启动时缓存 parent_bound=false 直接进入绑定页', (tester) async {
    final auth = FlowAuthRepository()..meResult = _a.copyWith(parentBound: false);
    final (c, _) = await pumpApp(tester, prefs: {
      'knoact_child_id': _a.id,
      'knoact_child_name': _a.name,
      'knoact_parent_bound': false,
      SessionStore.accessTokenKey: 'tok',
      SessionStore.refreshTokenKey: 'ref',
    }, auth: auth);
    expect(location(c), '/bind-parent');
  });

  testWidgets('会话失效（401）后回到登录页', (tester) async {
    final (c, _) = await pumpApp(tester);
    await login(tester, _a.name);
    expect(location(c), '/home');
    await c.read(sessionProvider.notifier).expire();
    await tester.pumpAndSettle();
    expect(location(c), '/login');
  });

  testWidgets('已登录访问未知路径跳到首页', (tester) async {
    final (c, _) = await pumpApp(tester, prefs: {
      'knoact_child_id': _a.id,
      'knoact_child_name': _a.name,
      SessionStore.accessTokenKey: 'tok',
      SessionStore.refreshTokenKey: 'ref',
    });
    expect(location(c), '/home');
    c.read(routerProvider).go('/nope');
    await tester.pumpAndSettle();
    expect(location(c), '/home');
    expect(find.text('金同学的阅读任务'), findsOneWidget);
  });
}
