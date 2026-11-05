import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/home/home_controller.dart';
import 'package:student_app/features/profile/ui/profile_page.dart';

import 'session_test.dart' show FakeAuthRepository;

const _me = Child(4, '金同学', loginName: 'jin', birthMonth: '2016-09', gender: 'female', interests: '画画,足球');

Future<(ProviderContainer, FakeAuthRepository)> pump(WidgetTester tester) async {
  SharedPreferences.setMockInitialValues({});
  tester.view.physicalSize = const Size(600, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final repo = FakeAuthRepository(_me);
  final container = ProviderContainer(
    overrides: [
      authRepositoryProvider.overrideWithValue(repo),
      pointsProvider.overrideWith((ref) async => 120),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await container.read(sessionProvider.notifier).login('jin', 'pw123456');
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: Scaffold(body: ProfilePage())),
  ));
  await tester.pumpAndSettle();
  return (container, repo);
}

String textOf(WidgetTester tester, String key) =>
    tester.widget<TextField>(find.byKey(Key(key))).controller!.text;

void main() {
  testWidgets('展示只读登录名并回填现有资料', (tester) async {
    await pump(tester);
    expect(find.text('登录名：jin'), findsOneWidget);
    expect(find.byKey(const Key('profileLoginName')), findsOneWidget);
    expect(textOf(tester, 'profileDisplayName'), '金同学');
    expect(textOf(tester, 'profileBirthMonth'), '2016-09');
    expect(textOf(tester, 'profileInterests'), '画画,足球');
    expect(find.text('女孩'), findsOneWidget);
  });

  testWidgets('保存资料调用接口并更新会话', (tester) async {
    final (c, repo) = await pump(tester);
    await tester.enterText(find.byKey(const Key('profileDisplayName')), '小金');
    await tester.enterText(find.byKey(const Key('profileBirthMonth')), '2015-03');
    await tester.enterText(find.byKey(const Key('profileInterests')), '编程， 游泳 篮球');
    await tester.tap(find.byKey(const Key('profileGender')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('男孩').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存资料'));
    await tester.pumpAndSettle();
    expect(repo.lastProfile, {'display_name': '小金', 'birth_month': '2015-03', 'gender': 'male', 'interests': '编程,游泳,篮球'});
    expect(c.read(sessionProvider).value!.name, '小金');
    expect(find.text('已保存'), findsOneWidget);
  });

  testWidgets('出生年月格式错误不提交', (tester) async {
    final (_, repo) = await pump(tester);
    await tester.enterText(find.byKey(const Key('profileBirthMonth')), '2015/03');
    await tester.tap(find.text('保存资料'));
    await tester.pumpAndSettle();
    expect(repo.lastProfile, isNull);
    expect(find.textContaining('YYYY-MM'), findsWidgets);
  });
}
