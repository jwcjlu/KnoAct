import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/auth/ui/login_page.dart';

import 'session_test.dart' show FakeAuthRepository;

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

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('名字为空时登录按钮不可用', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(const Child(4, '金同学')));
    final button = tester.widget<FilledButton>(find.widgetWithText(FilledButton, '开始学习'));
    expect(button.onPressed, isNull);
    expect(find.text('首次使用会自动创建账号，请确认名字无误'), findsOneWidget);
  });

  testWidgets('输入名字登录成功后会话有值', (tester) async {
    final c = await pumpLogin(tester, FakeAuthRepository(const Child(4, '金同学')));
    await tester.enterText(find.byType(TextField), '金同学');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
    await tester.pumpAndSettle();
    expect(c.read(sessionProvider).value, const Child(4, '金同学'));
  });

  testWidgets('家长名字提示不是孩子账号', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(NotAChildException()));
    await tester.enterText(find.byType(TextField), '金爸爸');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
    await tester.pumpAndSettle();
    expect(find.text('这个名字不是孩子账号，请输入孩子的名字'), findsOneWidget);
  });

  testWidgets('接口失败提示检查网络', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(ApiException('boom')));
    await tester.enterText(find.byType(TextField), '金同学');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
    await tester.pumpAndSettle();
    expect(find.text('登录失败，请检查网络或后端服务'), findsOneWidget);
  });

  testWidgets('小屏弹出键盘且显示错误时不溢出', (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(tester.view.reset);
    await pumpLogin(tester, FakeAuthRepository(ApiException('boom')));
    await tester.enterText(find.byType(TextField), '金同学');
    await tester.pump();
    final button = find.widgetWithText(FilledButton, '开始学习');
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('登录失败，请检查网络或后端服务'), findsOneWidget);
  });
}
