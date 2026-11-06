import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/core/router.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/auth/ui/login_page.dart';

import 'session_test.dart' show FakeAuthRepository, kChild;

Future<ProviderContainer> pumpLogin(WidgetTester tester, AuthRepository repo) async {
  final container = ProviderContainer(
    overrides: [authRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: LoginPage()),
  ));
  await tester.pumpAndSettle();
  return container;
}

Future<void> fill(WidgetTester tester, {String name = 'jin', String password = 'pw123456'}) async {
  await tester.enterText(find.byKey(const Key('loginName')), name);
  await tester.enterText(find.byKey(const Key('password')), password);
  await tester.pump();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('登录名或密码为空时登录按钮不可用', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(kChild));
    FilledButton button() => tester.widget<FilledButton>(find.widgetWithText(FilledButton, '登录'));
    expect(button().onPressed, isNull);
    await tester.enterText(find.byKey(const Key('loginName')), 'jin');
    await tester.pump();
    expect(button().onPressed, isNull);
    await tester.enterText(find.byKey(const Key('password')), 'pw123456');
    await tester.pump();
    expect(button().onPressed, isNotNull);
  });

  testWidgets('输入登录名和密码登录成功后会话有值', (tester) async {
    final repo = FakeAuthRepository(kChild);
    final c = await pumpLogin(tester, repo);
    await fill(tester);
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pumpAndSettle();
    expect(repo.lastLoginName, 'jin');
    expect(repo.lastPassword, 'pw123456');
    expect(c.read(sessionProvider).value, kChild);
  });

  testWidgets('账号密码错误提示', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(ApiException('401', statusCode: 401, code: 'invalid_credentials')));
    await fill(tester);
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pumpAndSettle();
    expect(find.text('登录名或密码不正确'), findsOneWidget);
  });

  testWidgets('家长账号提示不是孩子账号', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(NotAChildException()));
    await fill(tester, name: 'dad');
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pumpAndSettle();
    expect(find.text('这个账号不是孩子账号，请使用孩子的登录名'), findsOneWidget);
  });

  testWidgets('接口失败提示检查网络', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(ApiException('boom')));
    await fill(tester);
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pumpAndSettle();
    expect(find.text('登录失败，请检查网络或后端服务'), findsOneWidget);
  });

  testWidgets('登录页始终显示密码框', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(kChild));
    expect(find.byKey(const Key('password')), findsOneWidget);
    expect(find.text('账号登录'), findsOneWidget);
  });

  testWidgets('小屏弹出键盘且显示错误时不溢出', (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(tester.view.reset);
    await pumpLogin(tester, FakeAuthRepository(ApiException('boom')));
    await fill(tester);
    final button = find.widgetWithText(FilledButton, '登录');
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('登录失败，请检查网络或后端服务'), findsOneWidget);
  });

  testWidgets('登录页有去注册入口，可跳到注册页', (tester) async {
    final container = ProviderContainer(
      overrides: [authRepositoryProvider.overrideWithValue(FakeAuthRepository(kChild))],
      retry: (_, _) => null,
    );
    addTearDown(container.dispose);
    await container.read(sessionProvider.future);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: Consumer(builder: (_, ref, _) => MaterialApp.router(routerConfig: ref.watch(routerProvider))),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('还没有账号？去注册'));
    await tester.pumpAndSettle();
    expect(find.text('注册账号'), findsOneWidget);
    expect(container.read(routerProvider).routerDelegate.currentConfiguration.uri.path, '/register');
  });
}
