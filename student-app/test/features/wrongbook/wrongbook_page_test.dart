import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';
import 'package:student_app/features/wrongbook/data/wrongbook_models.dart';
import 'package:student_app/features/wrongbook/data/wrongbook_repository.dart';
import 'package:student_app/features/wrongbook/ui/wrongbook_page.dart';
import 'package:student_app/features/wrongbook/wrongbook_controller.dart';

import '../auth/session_test.dart' show FakeAuthRepository;

class FakeWrongbookRepository implements WrongbookRepository {
  FakeWrongbookRepository(this._buckets, this.mistakes);

  final List<BucketInfo> _buckets;
  final List<MistakeItem> mistakes;

  final corrected = <int>[];
  final listQueries = <int?>[];

  @override
  Future<List<MistakeItem>> list(int userId, {String subject = '', int? bucketId}) async {
    listQueries.add(bucketId);
    return mistakes;
  }

  @override
  Future<List<BucketInfo>> buckets(int userId) async => _buckets;

  @override
  Future<void> markCorrect(int id) async => corrected.add(id);

  @override
  Future<void> markWrong(int id) async {}
}

const _mistakes = [
  MistakeItem(
    id: 1,
    sourceType: 'reading',
    question: '桂花什么时候开？',
    yourAnswer: '春天',
    correctAnswer: '秋天',
    mistakeCount: 1,
    consecutiveCorrect: 0,
  ),
];

Future<(ProviderContainer, FakeWrongbookRepository)> pumpWrongbook(
  WidgetTester tester,
  FakeWrongbookRepository repo,
) async {
  SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
  tester.view.physicalSize = const Size(420, 1400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final container = ProviderContainer(
    overrides: [
      wrongbookRepositoryProvider.overrideWithValue(repo),
      authRepositoryProvider.overrideWithValue(FakeAuthRepository(const Child(4, '金同学'))),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: Scaffold(body: WrongbookPage())),
  ));
  // 真实 App 由 app_shell 在切到错题本 Tab 时触发 reload
  await container.read(wrongbookControllerProvider.notifier).reload();
  await tester.pumpAndSettle();
  return (container, repo);
}

void main() {
  testWidgets('只有一个桶时不显示学年选择器', (tester) async {
    final repo = FakeWrongbookRepository(
      const [BucketInfo(id: 9, grade: 4, schoolYear: '2026-2027', status: 'active')],
      _mistakes,
    );
    await pumpWrongbook(tester, repo);
    expect(find.byKey(const ValueKey('wrongbook-bucket-9')), findsNothing);
    expect(find.byKey(const ValueKey('wrongbook-readonly-banner')), findsNothing);
  });

  testWidgets('多个桶时显示学年选择器，选中归档桶禁用标记并显示只读提示', (tester) async {
    final repo = FakeWrongbookRepository(
      const [
        BucketInfo(id: 9, grade: 4, schoolYear: '2026-2027', status: 'active'),
        BucketInfo(id: 2, grade: 3, schoolYear: '2025-2026', status: 'archived'),
      ],
      _mistakes,
    );
    final (container, _) = await pumpWrongbook(tester, repo);

    // 两个学年 chip 都在，且默认选中 active 桶
    expect(find.text('2026-2027 · 4年级（当前）'), findsOneWidget);
    expect(find.text('2025-2026 · 3年级'), findsOneWidget);
    expect(container.read(wrongbookControllerProvider).bucketId, 9);
    expect(find.byKey(const ValueKey('wrongbook-readonly-banner')), findsNothing);

    // 切到归档桶
    await tester.tap(find.byKey(const ValueKey('wrongbook-bucket-2')));
    await tester.pumpAndSettle();
    expect(container.read(wrongbookControllerProvider).bucketId, 2);
    expect(container.read(wrongbookControllerProvider).isReadOnly, isTrue);
    expect(find.byKey(const ValueKey('wrongbook-readonly-banner')), findsOneWidget);
    expect(find.text('历史学年（只读）'), findsOneWidget);

    // 归档桶下「标记已掌握」禁用
    final button = tester.widget<FilledButton>(find.byKey(const ValueKey('mistake-master-1')));
    expect(button.onPressed, isNull);

    // 归档桶下调用 markMastered 也是 no-op
    container.read(wrongbookControllerProvider.notifier).markMastered(1);
    await tester.pumpAndSettle();
    expect(repo.corrected, isEmpty);
  });

  testWidgets('active 桶下「标记已掌握」可用', (tester) async {
    final repository = FakeWrongbookRepository(
      const [
        BucketInfo(id: 9, grade: 4, schoolYear: '2026-2027', status: 'active'),
        BucketInfo(id: 2, grade: 3, schoolYear: '2025-2026', status: 'archived'),
      ],
      _mistakes,
    );
    final (_, repo) = await pumpWrongbook(tester, repository);
    final button = tester.widget<FilledButton>(find.byKey(const ValueKey('mistake-master-1')));
    expect(button.onPressed, isNotNull);
    await tester.tap(find.byKey(const ValueKey('mistake-master-1')));
    await tester.pumpAndSettle();
    expect(repo.corrected, [1]);
  });
}
