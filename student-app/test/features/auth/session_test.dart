import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';

class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository(this.result);
  final Object result; // Child 或 Exception
  String? lastName;

  @override
  Future<Child> login(String name) async {
    lastName = name;
    if (result is Child) return result as Child;
    throw result;
  }
}

ProviderContainer makeContainer(AuthRepository repo) {
  final c = ProviderContainer(
    overrides: [authRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(c.dispose);
  return c;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('未登录时会话为 null', () async {
    final c = makeContainer(FakeAuthRepository(const Child(4, '金同学')));
    expect(await c.read(sessionProvider.future), isNull);
  });

  test('登录成功后保存并可在重建后恢复', () async {
    final repo = FakeAuthRepository(const Child(4, '金同学'));
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('  金同学 ');
    expect(repo.lastName, '金同学');
    expect(c.read(sessionProvider).value, const Child(4, '金同学'));

    final c2 = makeContainer(repo);
    expect(await c2.read(sessionProvider.future), const Child(4, '金同学'));
  });

  test('登录到非孩子账号时抛 NotAChildException 且不保存', () async {
    final c = makeContainer(FakeAuthRepository(NotAChildException()));
    await c.read(sessionProvider.future);
    await expectLater(c.read(sessionProvider.notifier).login('金爸爸'), throwsA(isA<NotAChildException>()));
    expect(c.read(sessionProvider).value, isNull);
  });

  test('退出登录清除保存', () async {
    final c = makeContainer(FakeAuthRepository(const Child(4, '金同学')));
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('金同学');
    await c.read(sessionProvider.notifier).logout();
    expect(c.read(sessionProvider).value, isNull);
    final c2 = makeContainer(FakeAuthRepository(const Child(4, '金同学')));
    expect(await c2.read(sessionProvider.future), isNull);
  });
}
