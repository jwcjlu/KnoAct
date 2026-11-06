import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/home/ui/home_page.dart';
import 'package:student_app/features/home/ui/home_sections.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';

import '../auth/session_test.dart' show FakeAuthRepository;

class FakeHomeRepository implements HomeRepository {
  FakeHomeRepository({this.fail = false, this.bucketList = const []});

  bool fail;
  final snapshotSubjects = <String>[];
  int redeemCalls = 0;
  bool redeemOk = true;
  int balanceValue = 350;
  final List<BucketInfo> bucketList;
  final balanceQueries = <int?>[];

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) async {
    if (fail) throw ApiException('boom');
    snapshotSubjects.add(subject);
    return HomeSnapshot(
      userName: '金同学',
      lessonProgress: LessonProgress(current: subject == '数学' ? 2 : 3, total: 8, mastered: 1, currentLessonId: 46),
    );
  }

  @override
  Future<List<StudyTask>> tasks(int userId, String date) async => const [
        StudyTask(id: 1, subject: '语文', taskType: 'dictation', title: '桂花雨 生词听写', detail: '', points: 20, submitStatus: 'approved'),
        StudyTask(id: 2, subject: '语文', taskType: 'reading', title: '桂花雨 阅读理解', detail: '', points: 20, submitStatus: 'not_started'),
        StudyTask(id: 3, subject: '语文', taskType: 'review', title: '到期复习', detail: '', points: 20, submitStatus: 'not_started'),
        StudyTask(id: 4, subject: '英语', taskType: 'listening', title: '英语听力', detail: '', points: 20, submitStatus: 'submitted'),
      ];

  @override
  Future<int> balance(int userId, {int? bucketId}) async {
    balanceQueries.add(bucketId);
    return balanceValue;
  }

  @override
  Future<List<BucketInfo>> buckets(int userId) async => bucketList;

  @override
  Future<bool> redeem(int userId, String device, int minutes) async {
    redeemCalls++;
    return redeemOk;
  }

  @override
  Future<void> submitTask(int taskId) async {}
}

Future<void> pumpHome(WidgetTester tester, FakeHomeRepository repo, {Size size = const Size(420, 900)}) async {
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final container = ProviderContainer(
    overrides: [
      homeRepositoryProvider.overrideWithValue(repo),
      authRepositoryProvider.overrideWithValue(FakeAuthRepository(const Child(4, '金同学'))),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: Scaffold(body: HomePage())),
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('显示问候、积分、课程与当前学科任务分组', (tester) async {
    await pumpHome(tester, FakeHomeRepository());
    expect(find.textContaining('金同学'), findsWidgets);
    expect(find.text('350'), findsWidgets);
    expect(find.textContaining('第 3 课重点学习与旧课复习'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('桂花雨 阅读理解'), 300);
    expect(find.text('待完成 2'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('已完成 1'), 300);
    expect(find.text('已完成 1'), findsOneWidget);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('task-action-1')), 300);
    expect(find.widgetWithText(FilledButton, '已完成'), findsOneWidget);
    expect(find.text('英语听力'), findsNothing);
  });

  testWidgets('切换学科重新拉取该学科快照', (tester) async {
    final repo = FakeHomeRepository();
    await pumpHome(tester, repo);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('subject-数学')), 300);
    await tester.tap(find.byKey(const ValueKey('subject-数学')));
    await tester.pumpAndSettle();
    expect(repo.snapshotSubjects.last, '数学');
    expect(find.textContaining('第 2 课重点学习与旧课复习'), findsOneWidget);
  });

  testWidgets('未实现的任务类型点击提示即将上线', (tester) async {
    await pumpHome(tester, FakeHomeRepository());
    final btn = find.byKey(const ValueKey('task-action-3'));
    await tester.scrollUntilVisible(btn, 300);
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pump();
    expect(find.text('该练习即将在 App 上线，可先在网页版完成'), findsOneWidget);
  });

  testWidgets('积分兑换成功提示并刷新积分', (tester) async {
    final repo = FakeHomeRepository();
    await pumpHome(tester, repo);
    repo.balanceValue = 50;
    final btn = find.byKey(const ValueKey('redeem-tablet'));
    await tester.scrollUntilVisible(btn, 300);
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pumpAndSettle();
    expect(repo.redeemCalls, 1);
    expect(find.text('已兑换平板 30 分钟，等待家长确认'), findsOneWidget);
    expect(find.text('当前 50 积分'), findsOneWidget);
  });

  testWidgets('学科标签与任务列表计数一致：无学科任务计入每个学科，无任务不显示 ✓', (tester) async {
    StudyTask t(int id, String subject, String status) =>
        StudyTask(id: id, subject: subject, taskType: 'custom', title: 't$id', detail: '', points: 20, submitStatus: status);
    Future<void> pumpTabs(List<StudyTask> tasks) => tester.pumpWidget(MaterialApp(
          home: Scaffold(body: SubjectTabs(tasks: tasks, current: '语文', onSelect: (_) {})),
        ));

    await pumpTabs([t(1, '语文', 'approved'), t(2, '英语', 'not_started'), t(3, '', 'not_started')]);
    expect(find.text('语文 1'), findsOneWidget);
    expect(find.text('英语 2'), findsOneWidget);
    expect(find.text('数学 1'), findsOneWidget);

    await pumpTabs([t(1, '语文', 'approved')]);
    expect(find.text('语文 ✓'), findsOneWidget);
    expect(find.text('英语'), findsOneWidget);
    expect(find.text('数学'), findsOneWidget);
  });

  testWidgets('加载失败显示重试', (tester) async {
    await pumpHome(tester, FakeHomeRepository(fail: true));
    expect(find.text('重试'), findsOneWidget);
  });

  testWidgets('只有一个桶时不显示学年选择器', (tester) async {
    final repo = FakeHomeRepository(
      bucketList: const [BucketInfo(id: 9, grade: 4, schoolYear: '2026-2027', status: 'active')],
    );
    await pumpHome(tester, repo);
    expect(find.byKey(const ValueKey('home-bucket-9')), findsNothing);
    expect(find.byKey(const ValueKey('home-bucket-readonly-banner')), findsNothing);
  });

  testWidgets('多个桶时显示学年选择器，切到历史桶更新积分查询', (tester) async {
    final repo = FakeHomeRepository(
      bucketList: const [
        BucketInfo(id: 9, grade: 4, schoolYear: '2026-2027', status: 'active'),
        BucketInfo(id: 2, grade: 3, schoolYear: '2025-2026', status: 'archived'),
      ],
    );
    await pumpHome(tester, repo);

    // 两个学年 chip 都在，默认选中 active 桶，不显示只读提示
    expect(find.text('2026-2027 · 4年级（当前）'), findsOneWidget);
    expect(find.text('2025-2026 · 3年级'), findsOneWidget);
    expect(find.byKey(const ValueKey('home-bucket-readonly-banner')), findsNothing);

    // 切到归档桶：显示历史学年提示，积分重新查询带 bucket_id
    await tester.tap(find.byKey(const ValueKey('home-bucket-2')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('home-bucket-readonly-banner')), findsOneWidget);
    expect(find.text('历史学年积分'), findsOneWidget);
    expect(repo.balanceQueries, contains(2));
  });
}
