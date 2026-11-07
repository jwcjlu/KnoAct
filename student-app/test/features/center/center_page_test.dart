import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
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
  Future<CenterMaterial> listening(int userId) async => const CenterMaterial(
        text: 'Hello Tom',
        questions: [
          CenterQuestion(
            'Who is Tom?',
            'Tom',
            options: ['Alice', 'Bob', 'Tom', 'Lily'],
            correctIndex: 2,
          ),
          CenterQuestion(
            'Who is Lily?',
            'Lily',
            options: ['Alice', 'Bob', 'Tom', 'Lily'],
            correctIndex: 3,
          ),
        ],
      );

  @override
  Future<CenterMaterial> reading(int userId) async => CenterMaterial.empty;

  @override
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {
    wrong.add('$sourceType:$question:$yourAnswer');
  }
}

class FakeHomeRepository implements HomeRepository {
  final submitted = <int>[];
  bool failSubmit = false;

  @override
  Future<void> uploadTaskPhoto(int taskId, List<int> bytes, {String filename = 'dictation.jpg'}) async {}

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

  @override
  Future<void> speak(String text) async => spoken.add(text);

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
  tester.view.physicalSize = const Size(420, 1200);
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

void main() {
  testWidgets('无任务时展示引导，不从 Tab 直接拉听力', (tester) async {
    final (container, _, _, _) = await pumpCenter(tester);
    await container.read(centerControllerProvider.notifier).enter();
    await tester.pumpAndSettle();
    expect(find.textContaining('学习首页'), findsOneWidget);
    expect(find.text('播放对话'), findsNothing);
  });

  testWidgets('听力任务：答错收录错题本，可播放对话', (tester) async {
    final (container, center, _, speech) = await pumpCenter(tester);
    final ctl = container.read(centerControllerProvider.notifier);
    ctl.openForTask(10);
    await ctl.enter();
    await tester.pumpAndSettle();
    expect(find.text('1. Who is Tom?'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('option-0-0')));
    await tester.pumpAndSettle();
    expect(center.wrong, ['listening:Who is Tom?:Alice']);

    await tester.tap(find.text('播放对话'));
    await tester.pumpAndSettle();
    expect(speech.spoken, ['Hello Tom']);
  });

  testWidgets('任务提交失败后显示重新提交并可重试', (tester) async {
    final (container, _, home, _) = await pumpCenter(tester);
    final ctl = container.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await tester.pumpAndSettle();
    home.failSubmit = true;
    await tester.tap(find.byKey(const ValueKey('option-0-2')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('option-1-3')));
    await tester.pumpAndSettle();
    expect(container.read(centerControllerProvider).submitFailed, isTrue);
    expect(find.text('重新提交'), findsOneWidget);

    home.failSubmit = false;
    await tester.dragUntilVisible(find.text('重新提交'), find.byType(ListView).first, const Offset(0, -200));
    await tester.pumpAndSettle();
    await tester.tap(find.text('重新提交'));
    await tester.pumpAndSettle();
    expect(home.submitted, [85]);
  });

  testWidgets('听力 Tab 不显示答案输入框', (tester) async {
    final (container, _, _, _) = await pumpCenter(tester);
    container.read(centerControllerProvider.notifier).openForTask(1);
    await container.read(centerControllerProvider.notifier).enter();
    await tester.pumpAndSettle();
    expect(find.text('输入你的答案'), findsNothing);
    expect(find.text('桂花开了'), findsNothing);
  });

}
