import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/center/speech_player.dart';
import 'package:student_app/features/center/ui/center_page.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';

import '../auth/session_test.dart' show FakeAuthRepository;

class FakeCenterRepository implements CenterRepository {
  final wrong = <String>[];

  @override
  Future<CenterMaterial> listening(int userId) async =>
      const CenterMaterial(text: 'Hello Tom', questions: [CenterQuestion('Who?', 'Tom')]);

  @override
  Future<CenterMaterial> reading(int userId) async =>
      const CenterMaterial(text: '桂花开了，满院飘香。', questions: [CenterQuestion('桂花什么时候开？', '秋天')]);

  @override
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {
    wrong.add('$sourceType:$question:$yourAnswer');
  }
}

class FakeHomeRepository implements HomeRepository {
  final submitted = <int>[];
  bool failSubmit = false;

  @override
  Future<void> submitTask(int taskId) async {
    if (failSubmit) throw Exception('submit failed');
    submitted.add(taskId);
  }

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) => throw UnimplementedError();
  @override
  Future<List<StudyTask>> tasks(int userId, String date) => throw UnimplementedError();
  @override
  Future<int> balance(int userId, {int? bucketId}) => throw UnimplementedError();
  @override
  Future<List<BucketInfo>> buckets(int userId) async => const [];
  @override
  Future<bool> redeem(int userId, String device, int minutes) => throw UnimplementedError();
}

class FakeSpeechPlayer implements SpeechPlayer {
  final spoken = <String>[];
  bool failSpeak = false;

  @override
  Future<void> speak(String text) async {
    if (failSpeak) throw Exception('speak failed');
    spoken.add(text);
  }

  @override
  Future<void> stop() async {}

  @override
  Future<void> dispose() async {}
}

Future<(ProviderContainer, FakeCenterRepository, FakeHomeRepository, FakeSpeechPlayer)> pumpCenter(WidgetTester tester) async {
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  // 阅读页含个性化学习入口 + 课文 + 对话栏 + 题目 + 提交按钮，用较高窗口避免按钮被挤出屏幕
  tester.view.physicalSize = const Size(420, 1400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final center = FakeCenterRepository();
  final home = FakeHomeRepository();
  final speech = FakeSpeechPlayer();
  final container = ProviderContainer(
    overrides: [
      centerRepositoryProvider.overrideWithValue(center),
      homeRepositoryProvider.overrideWithValue(home),
      speechPlayerProvider.overrideWithValue(speech),
      authRepositoryProvider.overrideWithValue(FakeAuthRepository(const Child(4, '金同学'))),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: Scaffold(body: CenterPage())),
  ));
  return (container, center, home, speech);
}

FilledButton submitButton(WidgetTester tester, int index) =>
    tester.widget<FilledButton>(find.byKey(ValueKey('submit-$index')));

void main() {
  testWidgets('阅读答题提示收录错题本，听力播放对话', (tester) async {
    final (container, center, _, speech) = await pumpCenter(tester);

    container.read(centerControllerProvider.notifier).selectTab(CenterTab.reading);
    await tester.pumpAndSettle();
    expect(find.text('桂花开了，满院飘香。'), findsOneWidget);
    expect(find.text('1. 桂花什么时候开？'), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('answer-0')), '春天');
    await tester.pump();
    await tester.ensureVisible(find.byKey(const ValueKey('submit-0')));
    await tester.tap(find.byKey(const ValueKey('submit-0')));
    await tester.pumpAndSettle();
    expect(find.text('答错了，已收录进错题本'), findsOneWidget);
    expect(find.text('✗ 答案：秋天'), findsOneWidget);
    expect(center.wrong, ['reading:桂花什么时候开？:春天']);

    await tester.tap(find.text(CenterTab.listening.label));
    await tester.pumpAndSettle();
    await tester.tap(find.text('播放对话'));
    await tester.pumpAndSettle();
    expect(speech.spoken, ['Hello Tom']);
  });

  testWidgets('答案为空时不能提交，键盘完成键可提交', (tester) async {
    final (container, center, _, _) = await pumpCenter(tester);
    container.read(centerControllerProvider.notifier).selectTab(CenterTab.reading);
    await tester.pumpAndSettle();

    expect(submitButton(tester, 0).onPressed, isNull);
    await tester.enterText(find.byKey(const ValueKey('answer-0')), '   ');
    await tester.pumpAndSettle();
    expect(submitButton(tester, 0).onPressed, isNull);
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(center.wrong, isEmpty);
    expect(find.byKey(const ValueKey('answer-0')), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('answer-0')), '春天');
    await tester.pumpAndSettle();
    expect(submitButton(tester, 0).onPressed, isNotNull);
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(center.wrong, ['reading:桂花什么时候开？:春天']);
    expect(find.text('✗ 答案：秋天'), findsOneWidget);
  });

  testWidgets('任务提交失败后显示重新提交并可重试', (tester) async {
    final (container, _, home, _) = await pumpCenter(tester);
    final ctl = container.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    ctl.enter();
    await tester.pumpAndSettle();
    home.failSubmit = true;
    await tester.enterText(find.byKey(const ValueKey('answer-0')), '秋天');
    await tester.pump();
    await tester.ensureVisible(find.byKey(const ValueKey('submit-0')));
    await tester.tap(find.byKey(const ValueKey('submit-0')));
    await tester.pumpAndSettle();
    expect(find.text('提交任务失败，请稍后重试'), findsOneWidget);
    expect(find.text('重新提交'), findsOneWidget);

    home.failSubmit = false;
    await tester.dragUntilVisible(find.text('重新提交'), find.byType(ListView).first, const Offset(0, -200));
    await tester.pumpAndSettle();
    await tester.tap(find.text('重新提交'));
    await tester.pumpAndSettle();
    expect(home.submitted, [85]);
    expect(find.text('重新提交'), findsNothing);
    expect(find.text('已提交，等待家长确认'), findsOneWidget);
  });

  testWidgets('播放失败时提示', (tester) async {
    final (container, _, _, speech) = await pumpCenter(tester);
    container.read(centerControllerProvider.notifier).enter();
    await tester.pumpAndSettle();
    speech.failSpeak = true;
    await tester.tap(find.text('播放对话'));
    await tester.pumpAndSettle();
    expect(find.text('播放失败，请稍后重试'), findsOneWidget);
  });
}
