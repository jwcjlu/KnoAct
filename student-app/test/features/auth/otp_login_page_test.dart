import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/auth/ui/otp_login_page.dart';

import 'session_test.dart' show FakeAuthRepository, kChild;

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('验证码登录页发送并登录', (tester) async {
    final repo = FakeAuthRepository(kChild);
    final c = ProviderContainer(
      overrides: [authRepositoryProvider.overrideWithValue(repo)],
      retry: (_, _) => null,
    );
    addTearDown(c.dispose);
    await c.read(sessionProvider.future);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: c,
      child: const MaterialApp(home: OtpLoginPage()),
    ));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'jin');
    await tester.pump();
    await tester.tap(find.text('发送验证码'));
    await tester.pumpAndSettle();
    expect(repo.otpSent, isTrue);
    await tester.enterText(find.byType(TextField).at(1), '123456');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pumpAndSettle();
    expect(repo.lastCode, '123456');
    expect(c.read(sessionProvider).value, kChild);
  });
}
