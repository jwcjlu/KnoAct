import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/auth/ui/bind_parent_page.dart';
import 'package:student_app/features/auth/ui/register_page.dart';

import 'session_test.dart' show FakeAuthRepository;

const _unbound = Child(9, '新同学', loginName: 'newbie', parentBound: false);

Future<ProviderContainer> pump(WidgetTester tester, FakeAuthRepository repo, Widget page, {bool signedIn = false}) async {
  final container = ProviderContainer(
    overrides: [authRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  if (signedIn) await container.read(sessionProvider.notifier).login('newbie', 'pw123456');
  await tester.pumpWidget(UncontrolledProviderScope(container: container, child: MaterialApp(home: page)));
  await tester.pumpAndSettle();
  return container;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('RegisterPage', () {
    testWidgets('两次密码不一致时不能提交', (tester) async {
      await pump(tester, FakeAuthRepository(_unbound), const RegisterPage());
      await tester.enterText(find.byKey(const Key('registerLoginName')), 'newbie');
      await tester.enterText(find.byKey(const Key('registerPassword')), 'pw123456');
      await tester.enterText(find.byKey(const Key('registerConfirm')), 'other');
      await tester.pump();
      expect(find.text('两次输入的密码不一致'), findsOneWidget);
      expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, '注册')).onPressed, isNull);
    });

    testWidgets('注册成功后会话建立且未绑定家长', (tester) async {
      final repo = FakeAuthRepository(_unbound);
      final c = await pump(tester, repo, const RegisterPage());
      await tester.enterText(find.byKey(const Key('registerLoginName')), 'newbie');
      await tester.enterText(find.byKey(const Key('registerPassword')), 'pw123456');
      await tester.enterText(find.byKey(const Key('registerConfirm')), 'pw123456');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, '注册'));
      await tester.pumpAndSettle();
      expect(repo.lastRegisterName, 'newbie');
      expect(c.read(sessionProvider).value, _unbound);
    });

    testWidgets('登录名被占用提示', (tester) async {
      await pump(tester, FakeAuthRepository(ApiException('409', statusCode: 409, code: 'login_name_taken')), const RegisterPage());
      await tester.enterText(find.byKey(const Key('registerLoginName')), 'newbie');
      await tester.enterText(find.byKey(const Key('registerPassword')), 'pw123456');
      await tester.enterText(find.byKey(const Key('registerConfirm')), 'pw123456');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, '注册'));
      await tester.pumpAndSettle();
      expect(find.text('这个登录名已被使用，换一个试试'), findsOneWidget);
    });
  });

  group('BindParentPage', () {
    testWidgets('邀请码绑定成功后会话 parent_bound 变 true', (tester) async {
      final repo = FakeAuthRepository(_unbound);
      final c = await pump(tester, repo, const BindParentPage(), signedIn: true);
      expect(c.read(sessionProvider).value!.parentBound, isFalse);
      repo.meResult = const Child(9, '新同学', loginName: 'newbie');
      await tester.enterText(find.byKey(const Key('inviteCode')), 'ab12cd34');
      await tester.pump();
      await tester.tap(find.text('用邀请码绑定'));
      await tester.pumpAndSettle();
      expect(repo.lastBindCode, 'ab12cd34');
      expect(c.read(sessionProvider).value!.parentBound, isTrue);
    });

    testWidgets('邀请码无效提示', (tester) async {
      final repo = FakeAuthRepository(_unbound);
      await pump(tester, repo, const BindParentPage(), signedIn: true);
      repo.meResult = ApiException('404', statusCode: 404, code: 'invalid_code');
      await tester.enterText(find.byKey(const Key('inviteCode')), 'zzzz');
      await tester.pump();
      await tester.tap(find.text('用邀请码绑定'));
      await tester.pumpAndSettle();
      expect(find.text('验证码或邀请码不正确'), findsOneWidget);
    });

    testWidgets('按家长登录名发申请，提示等待审批', (tester) async {
      final repo = FakeAuthRepository(_unbound);
      final c = await pump(tester, repo, const BindParentPage(), signedIn: true);
      await tester.enterText(find.byKey(const Key('parentLoginName')), 'mom');
      await tester.pump();
      await tester.tap(find.text('向家长发送申请'));
      await tester.pumpAndSettle();
      expect(repo.lastParentLoginName, 'mom');
      expect(find.textContaining('申请已发送'), findsOneWidget);
      expect(c.read(sessionProvider).value!.parentBound, isFalse);
    });

    testWidgets('可退出登录', (tester) async {
      final c = await pump(tester, FakeAuthRepository(_unbound), const BindParentPage(), signedIn: true);
      await tester.tap(find.text('退出登录'));
      await tester.pumpAndSettle();
      expect(c.read(sessionProvider).value, isNull);
    });
  });
}
