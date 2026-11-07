import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/data/auth_repository.dart' show AuthSession;
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/center/speech_player.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/wrongbook/data/bucket_models.dart';

import '../auth/session_test.dart' show FakeAuthRepository;

const _mcOpts = ['a', 'b', 'c', 'd'];
const _childJin = '\u91d1\u540c\u5b66';
const _childLi = '\u674e\u540c\u5b66';
const _msgWrong = '\u7b54\u9519\u4e86\uff0c\u5df2\u6536\u5f55\u8fdb\u9519\u9898\u672c';
const _msgSubmitted = '\u5df2\u63d0\u4ea4\uff0c\u7b49\u5f85\u5bb6\u957f\u786e\u8ba4';
const _msgNoMaterial = '\u6682\u65e0\u6750\u6599\uff0c\u6682\u65f6\u65e0\u6cd5\u5b8c\u6210\u8be5\u4efb\u52a1';
const _msgSubmitFail = '\u63d0\u4ea4\u4efb\u52a1\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5';
const _msgWrongAndSubmitted =
    '\u7b54\u9519\u4e86\uff0c\u5df2\u6536\u5f55\u8fdb\u9519\u9898\u672c\uff1b\u4efb\u52a1\u5df2\u63d0\u4ea4\uff0c\u7b49\u5f85\u5bb6\u957f\u786e\u8ba4';
const _msgWrongAndSubmitFail =
    '\u7b54\u9519\u4e86\uff0c\u5df2\u6536\u5f55\u8fdb\u9519\u9898\u672c\uff1b\u63d0\u4ea4\u4efb\u52a1\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5';
const _msgWrongFailAndSubmitted =
    '\u7b54\u9519\u4e86\uff08\u6536\u5f55\u9519\u9898\u672c\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\uff09\uff1b\u4efb\u52a1\u5df2\u63d0\u4ea4\uff0c\u7b49\u5f85\u5bb6\u957f\u786e\u8ba4';
const _msgSubmitFailRestart =
    '\u63d0\u4ea4\u4efb\u52a1\u5931\u8d25\uff0c\u8bf7\u56de\u9996\u9875\u91cd\u65b0\u5f00\u59cb\u8be5\u4efb\u52a1';

class FakeCenterRepository implements CenterRepository {
  CenterMaterial readingMaterial = const CenterMaterial(text: '\u8bfe\u6587', questions: [CenterQuestion('Q1', 'A1')]);
  CenterMaterial listeningMaterial = const CenterMaterial(
    text: 'Hi',
    questions: [
      CenterQuestion('L1', 'b', options: _mcOpts, correctIndex: 1),
      CenterQuestion('L2', 'd', options: _mcOpts, correctIndex: 3),
    ],
  );
  final wrong = <String>[];

  Completer<void>? wrongGate;
  bool failWrong = false;

  Completer<void>? materialGate;
  int loads = 0;

  Future<CenterMaterial> _material(CenterMaterial m) async {
    loads++;
    final gate = materialGate;
    if (gate != null) await gate.future;
    return m;
  }

  @override
  Future<CenterMaterial> listening(int userId) => _material(listeningMaterial);

  @override
  Future<CenterMaterial> reading(int userId) => _material(readingMaterial);

  @override
  Future<void> submitWrong({
    required int userId,
    required String question,
    required String yourAnswer,
    required String correctAnswer,
    required String sourceType,
  }) async {
    wrong.add('$sourceType:$question:$yourAnswer');
    final gate = wrongGate;
    if (gate != null) await gate.future;
    if (failWrong) throw Exception('wrong failed');
  }
}

class FakeTaskRepository implements HomeRepository {
  final submitted = <int>[];

  Completer<void>? submitGate;
  bool failSubmit = false;
  int homeLoads = 0;

  @override
  Future<void> submitTask(int taskId) async {
    final gate = submitGate;
    if (gate != null) await gate.future;
    if (failSubmit) throw Exception('submit failed');
    submitted.add(taskId);
  }

  @override
  Future<void> uploadTaskPhoto(int taskId, List<int> bytes, {String filename = 'dictation.jpg'}) async {}

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) {
    homeLoads++;
    throw UnimplementedError();
  }

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
  int stops = 0;

  @override
  Future<void> speak(String text) async {}

  @override
  Future<void> stop() async => stops++;

  @override
  Future<void> dispose() async {}
}

late FakeSpeechPlayer speech;

class CenterFlowAuth extends FakeAuthRepository {
  CenterFlowAuth() : super(Child(4, _childJin, loginName: 'jin'));

  @override
  Future<AuthSession> login(String loginName, String password) async {
    lastLoginName = loginName;
    lastPassword = password;
    final child = loginName == 'li'
        ? Child(5, _childLi, loginName: 'li')
        : Child(4, _childJin, loginName: 'jin');
    return AuthSession(child, accessToken: 'acc-1', refreshToken: 'ref-1');
  }
}

Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository)> setup() async {
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': _childJin,
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  final center = FakeCenterRepository();
  final tasks = FakeTaskRepository();
  speech = FakeSpeechPlayer();
  final c = ProviderContainer(
    overrides: [
      centerRepositoryProvider.overrideWithValue(center),
      homeRepositoryProvider.overrideWithValue(tasks),
      speechPlayerProvider.overrideWithValue(speech),
      authRepositoryProvider.overrideWithValue(CenterFlowAuth()),
    ],
    retry: (_, _) => null,
  );
  addTearDown(c.dispose);
  await c.read(sessionProvider.future);
  return (c, center, tasks);
}

void main() {
  test('?????????????', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.enter();
    final s = c.read(centerControllerProvider);
    expect(s.tab, CenterTab.listening);
    expect(s.material.value!.isEmpty, isTrue);
    expect(center.loads, 0);
  });

  test('????????????', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    final s = c.read(centerControllerProvider);
    expect(s.material.value!.questions.length, 2);
    expect(s.results, [null, null]);
  });

  test('?????????????????', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 0);
    expect(center.wrong, ['listening:L1:a']);
    expect(c.read(centerControllerProvider).message, _msgWrong);
    expect(c.read(centerControllerProvider).results, [false, null]);
    await ctl.answer(0, selectedIndex: 1);
    expect(center.wrong.length, 1);
  });

  test('?????????????????', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    expect(c.read(centerControllerProvider).tab, CenterTab.listening);
    await ctl.answer(0, selectedIndex: 1);
    expect(tasks.submitted, isEmpty);
    await ctl.answer(1, selectedIndex: 3);
    expect(tasks.submitted, [85]);
    expect(c.read(centerControllerProvider).message, _msgSubmitted);
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('?????????????', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    ctl.leave();
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('???????????', () async {
    final (c, center, tasks) = await setup();
    center.listeningMaterial = CenterMaterial.empty;
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    expect(c.read(centerControllerProvider).message, _msgNoMaterial);
    expect(tasks.submitted, isEmpty);
  });

  test('?????????', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 0);
    await ctl.answer(0, selectedIndex: 2);
    expect(center.wrong.length, 1);
  });

  test('??????????????????', () async {
    final (c, center, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 1);
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(1, selectedIndex: 0);
    ctl.leave();
    gate.complete();
    await answering;
    expect(tasks.submitted, [85]);
  });

  test('?????????????????????????', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 1);
    final gate = tasks.submitGate = Completer<void>();
    final first = ctl.answer(1, selectedIndex: 3);
    tasks.submitGate = null;
    ctl.openForTask(86);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 1);
    await ctl.answer(1, selectedIndex: 3);
    expect(tasks.submitted, isEmpty);
    gate.complete();
    await first;
    expect(tasks.submitted, [85, 86]);
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('??????????????', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 0);
    ctl.openForTask(86);
    final s = c.read(centerControllerProvider);
    expect(s.material.isLoading, isTrue);
    expect(s.material.hasValue, isFalse);
    expect(s.results, isEmpty);
    expect(s.inputs, isEmpty);
  });

  test('???????????', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 1);
    expect(tasks.homeLoads, 0);
    await ctl.answer(1, selectedIndex: 3);
    expect(tasks.submitted, [85]);
    expect(tasks.homeLoads, greaterThan(0));
  });

  test('reload ??????????????', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(0, selectedIndex: 0);
    await ctl.reload();
    gate.complete();
    await answering;
    expect(c.read(centerControllerProvider).message, isNot(_msgWrong));
  });

  test('setInput ??????', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    ctl.setInput(5, 'x');
    ctl.setInput(-1, 'x');
    expect(c.read(centerControllerProvider).inputs, ['', '']);
  });

  test('?????????', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    tasks.failSubmit = true;
    await ctl.answer(0, selectedIndex: 1);
    await ctl.answer(1, selectedIndex: 3);
    var s = c.read(centerControllerProvider);
    expect(s.message, _msgSubmitFail);
    expect(s.submitFailed, isTrue);
    expect(s.pending?.taskId, 85);
    tasks.failSubmit = false;
    await ctl.retrySubmit();
    s = c.read(centerControllerProvider);
    expect(tasks.submitted, [85]);
    expect(s.submitFailed, isFalse);
    expect(s.pending, isNull);
  });

  test('???????????', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    ctl.leave();
    expect(speech.stops, 1);
  });

  Future<void> switchChild(ProviderContainer c) async {
    await c.read(sessionProvider.notifier).logout();
    await c.read(sessionProvider.notifier).login('li', 'pw123456');
  }

  test('????????????????????????????', () async {
    final (c, center, _) = await setup();
    c.listen(centerControllerProvider, (_, _) {});
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    final gate = center.materialGate = Completer<void>();
    final loading = ctl.enter();
    await switchChild(c);
    expect(c.read(centerControllerProvider).pending, isNull);
    expect(speech.stops, greaterThan(0));
    gate.complete();
    await loading;
    final s = c.read(centerControllerProvider);
    expect(s.material.hasValue, isFalse);
    expect(s.results, isEmpty);
  });

  test('??????????????????????', () async {
    final (c, center, _) = await setup();
    c.listen(centerControllerProvider, (_, _) {});
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(0, selectedIndex: 0);
    await switchChild(c);
    gate.complete();
    await answering;
    expect(c.read(centerControllerProvider).message, isNull);
  });

  test('?????????????????', () async {
    final (c, center, _) = await setup();
    await c.read(sessionProvider.notifier).logout();
    await c.read(centerControllerProvider.notifier).enter();
    expect(center.loads, 0);
    expect(c.read(centerControllerProvider).material.hasError, isFalse);
  });

  Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository, CenterController)> lastQuestionPending() async {
    final (c, center, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85);
    await ctl.enter();
    await ctl.answer(0, selectedIndex: 1);
    return (c, center, tasks, ctl);
  }

  test('??????????????????????????????', () async {
    final (c, center, tasks, ctl) = await lastQuestionPending();
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(1, selectedIndex: 0);
    await pumpEventQueue();
    var s = c.read(centerControllerProvider);
    expect(tasks.submitted, [85]);
    expect(s.submitting, isFalse);
    expect(s.pending, isNull);
    expect(tasks.homeLoads, greaterThan(0));
    gate.complete();
    await answering;
    s = c.read(centerControllerProvider);
    expect(s.message, _msgWrongAndSubmitted);
  });

  test('??????????????????????', () async {
    final (c, _, tasks, ctl) = await lastQuestionPending();
    tasks.failSubmit = true;
    await ctl.answer(1, selectedIndex: 0);
    final s = c.read(centerControllerProvider);
    expect(s.message, _msgWrongAndSubmitFail);
    expect(s.submitFailed, isTrue);
  });

  test('?????????????????????', () async {
    final (c, center, _, ctl) = await lastQuestionPending();
    center.failWrong = true;
    await ctl.answer(1, selectedIndex: 0);
    expect(
      c.read(centerControllerProvider).message,
      _msgWrongFailAndSubmitted,
    );
  });

  test('????????????????????', () async {
    final (c, _, tasks, ctl) = await lastQuestionPending();
    final gate = tasks.submitGate = Completer<void>();
    tasks.failSubmit = true;
    final first = ctl.answer(1, selectedIndex: 3);
    ctl.openForTask(86);
    gate.complete();
    await first;
    final s = c.read(centerControllerProvider);
    expect(s.message, _msgSubmitFailRestart);
    expect(s.submitFailed, isFalse);
    expect(s.pending?.taskId, 86);
  });
}
