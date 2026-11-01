import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/center/speech_player.dart';
import 'package:student_app/features/center/ui/center_page.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';

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
  @override
  Future<void> submitTask(int taskId) async {}

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) => throw UnimplementedError();
  @override
  Future<List<StudyTask>> tasks(int userId, String date) => throw UnimplementedError();
  @override
  Future<int> balance(int userId) => throw UnimplementedError();
  @override
  Future<bool> redeem(int userId, String device, int minutes) => throw UnimplementedError();
}

class FakeSpeechPlayer implements SpeechPlayer {
  final spoken = <String>[];

  @override
  Future<void> speak(String text) async => spoken.add(text);

  @override
  Future<void> dispose() async {}
}

void main() {
  testWidgets('阅读答题提示收录错题本，听力播放对话', (tester) async {
    SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
    final center = FakeCenterRepository();
    final speech = FakeSpeechPlayer();
    final container = ProviderContainer(
      overrides: [
        centerRepositoryProvider.overrideWithValue(center),
        homeRepositoryProvider.overrideWithValue(FakeHomeRepository()),
        speechPlayerProvider.overrideWithValue(speech),
      ],
      retry: (_, _) => null,
    );
    addTearDown(container.dispose);
    await container.read(sessionProvider.future);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: Scaffold(body: CenterPage())),
    ));

    container.read(centerControllerProvider.notifier).selectTab(CenterTab.reading);
    await tester.pumpAndSettle();
    expect(find.text('桂花开了，满院飘香。'), findsOneWidget);
    expect(find.text('1. 桂花什么时候开？'), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('answer-0')), '春天');
    await tester.tap(find.byKey(const ValueKey('submit-0')));
    await tester.pump();
    await tester.pump();
    expect(find.text('答错了，已收录进错题本'), findsOneWidget);
    expect(find.text('✗ 答案：秋天'), findsOneWidget);
    expect(center.wrong, ['reading:桂花什么时候开？:春天']);

    await tester.tap(find.text(CenterTab.listening.label));
    await tester.pumpAndSettle();
    await tester.tap(find.text('播放对话'));
    await tester.pump();
    expect(speech.spoken, ['Hello Tom']);
  });
}
