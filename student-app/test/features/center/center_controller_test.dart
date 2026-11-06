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

class FakeCenterRepository implements CenterRepository {
  CenterMaterial readingMaterial = const CenterMaterial(text: '课文', questions: [CenterQuestion('Q1', 'A1'), CenterQuestion('Q2', 'A2')]);
  CenterMaterial listeningMaterial = const CenterMaterial(text: 'Hi', questions: [CenterQuestion('L1', 'yes')]);
  final wrong = <String>[];

  /// 非空时 submitWrong 等待它完成后才返回
  Completer<void>? wrongGate;
  bool failWrong = false;

  /// 非空时拉取材料等待它完成后才返回
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
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {
    wrong.add('$sourceType:$question:$yourAnswer');
    final gate = wrongGate;
    if (gate != null) await gate.future;
    if (failWrong) throw Exception('wrong failed');
  }
}

class FakeTaskRepository implements HomeRepository {
  final submitted = <int>[];

  /// 非空时 submitTask 等待它完成后才返回
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

/// 与 [switchChild] 测试一致：`jin`→金同学、`li`→李同学
class CenterFlowAuth extends FakeAuthRepository {
  CenterFlowAuth() : super(const Child(4, '金同学', loginName: 'jin'));

  @override
  Future<AuthSession> login(String loginName, String password) async {
    lastLoginName = loginName;
    lastPassword = password;
    final child = loginName == 'li'
        ? const Child(5, '李同学', loginName: 'li')
        : const Child(4, '金同学', loginName: 'jin');
    return AuthSession(child, accessToken: 'acc-1', refreshToken: 'ref-1');
  }
}

Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository)> setup() async {
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
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
  test('进入时加载当前 Tab 材料并清空作答', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.enter();
    final s = c.read(centerControllerProvider);
    expect(s.tab, CenterTab.listening);
    expect(s.material.value!.questions.length, 1);
    expect(s.results, [null]);
  });

  test('答错收录错题本并提示，答对提示正确', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.selectTab(CenterTab.reading);
    await ctl.answer(0, 'x');
    expect(center.wrong, ['reading:Q1:x']);
    expect(c.read(centerControllerProvider).message, '答错了，已收录进错题本');
    await ctl.answer(1, ' A2 ');
    expect(c.read(centerControllerProvider).message, '回答正确！');
    expect(c.read(centerControllerProvider).results, [false, true]);
  });

  test('从任务进入：在任务对应 Tab 全部作答后自动提交一次', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    expect(c.read(centerControllerProvider).tab, CenterTab.reading);
    await ctl.answer(0, 'A1');
    expect(tasks.submitted, isEmpty);
    await ctl.answer(1, 'A2');
    expect(tasks.submitted, [85]);
    expect(c.read(centerControllerProvider).message, '已提交，等待家长确认');
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('切到别的 Tab 后清除待提交任务', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    await ctl.selectTab(CenterTab.listening);
    expect(c.read(centerControllerProvider).pending, isNull);
    await ctl.selectTab(CenterTab.reading);
    await ctl.answer(0, 'A1');
    await ctl.answer(1, 'A2');
    expect(tasks.submitted, isEmpty);
  });

  test('离开学习中心清除待提交任务', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    ctl.leave();
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('材料为空时不提交并提示', () async {
    final (c, center, tasks) = await setup();
    center.readingMaterial = CenterMaterial.empty;
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    expect(c.read(centerControllerProvider).message, '暂无材料，暂时无法完成该任务');
    expect(tasks.submitted, isEmpty);
  });

  test('同一题只能作答一次', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.selectTab(CenterTab.reading);
    await ctl.answer(0, 'x');
    await ctl.answer(0, 'y');
    expect(center.wrong.length, 1);
  });

  test('最后一题答错后立即离开，任务仍会提交', () async {
    final (c, center, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    await ctl.answer(0, 'A1');
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(1, 'x');
    ctl.leave();
    gate.complete();
    await answering;
    expect(tasks.submitted, [85]);
  });

  test('旧任务提交完成时不清除新任务，且新任务随后自动提交', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    await ctl.answer(0, 'A1');
    final gate = tasks.submitGate = Completer<void>();
    final first = ctl.answer(1, 'A2');
    tasks.submitGate = null;
    ctl.openForTask(86, CenterTab.reading);
    await ctl.enter();
    await ctl.answer(0, 'A1');
    await ctl.answer(1, 'A2');
    expect(tasks.submitted, isEmpty);
    gate.complete();
    await first;
    expect(tasks.submitted, [85, 86]);
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('从任务进入时清空旧材料与作答', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.enter();
    await ctl.answer(0, 'yes');
    ctl.openForTask(85, CenterTab.reading);
    final s = c.read(centerControllerProvider);
    expect(s.material.isLoading, isTrue);
    expect(s.material.hasValue, isFalse);
    expect(s.results, isEmpty);
    expect(s.inputs, isEmpty);
  });

  test('任务提交成功后刷新首页', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    await ctl.answer(0, 'A1');
    expect(tasks.homeLoads, 0);
    await ctl.answer(1, 'A2');
    expect(tasks.submitted, [85]);
    expect(tasks.homeLoads, greaterThan(0));
  });

  test('切换 Tab 后，过期的错题收录结果不再提示', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.selectTab(CenterTab.reading);
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(0, 'x');
    await ctl.selectTab(CenterTab.listening);
    gate.complete();
    await answering;
    expect(c.read(centerControllerProvider).message, isNot('答错了，已收录进错题本'));
  });

  test('setInput 忽略越界下标', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.enter();
    ctl.setInput(5, 'x');
    ctl.setInput(-1, 'x');
    expect(c.read(centerControllerProvider).inputs, ['']);
  });

  test('任务提交失败可重试', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    tasks.failSubmit = true;
    await ctl.answer(0, 'A1');
    await ctl.answer(1, 'A2');
    var s = c.read(centerControllerProvider);
    expect(s.message, '提交任务失败，请稍后重试');
    expect(s.submitFailed, isTrue);
    expect(s.pending?.taskId, 85);
    tasks.failSubmit = false;
    await ctl.retrySubmit();
    s = c.read(centerControllerProvider);
    expect(tasks.submitted, [85]);
    expect(s.submitFailed, isFalse);
    expect(s.pending, isNull);
  });

  test('离开学习中心或切到阅读时停止朗读', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.enter();
    ctl.leave();
    expect(speech.stops, 1);
    await ctl.selectTab(CenterTab.reading);
    expect(speech.stops, 2);
  });

  Future<void> switchChild(ProviderContainer c) async {
    await c.read(sessionProvider.notifier).logout();
    await c.read(sessionProvider.notifier).login('li', 'pw123456');
  }

  test('切换孩子：状态重置并停止朗读，上一个孩子的在途材料不写入', () async {
    final (c, center, _) = await setup();
    c.listen(centerControllerProvider, (_, _) {});
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
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

  test('切换孩子后，上一个孩子的错题收录提示不再出现', () async {
    final (c, center, _) = await setup();
    c.listen(centerControllerProvider, (_, _) {});
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.selectTab(CenterTab.reading);
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(0, 'x');
    await switchChild(c);
    gate.complete();
    await answering;
    expect(c.read(centerControllerProvider).message, isNull);
  });

  test('未登录时进入学习中心不请求也不报错', () async {
    final (c, center, _) = await setup();
    await c.read(sessionProvider.notifier).logout();
    await c.read(centerControllerProvider.notifier).enter();
    expect(center.loads, 0);
    expect(c.read(centerControllerProvider).material.hasError, isFalse);
  });

  Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository, CenterController)> lastQuestionPending() async {
    final (c, center, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    await ctl.answer(0, 'A1');
    return (c, center, tasks, ctl);
  }

  test('最后一题答错：提交返回即解除提交中并刷新首页，提示合并为一条', () async {
    final (c, center, tasks, ctl) = await lastQuestionPending();
    final gate = center.wrongGate = Completer<void>();
    final answering = ctl.answer(1, 'x');
    await pumpEventQueue();
    var s = c.read(centerControllerProvider);
    expect(tasks.submitted, [85]);
    expect(s.submitting, isFalse);
    expect(s.pending, isNull);
    expect(tasks.homeLoads, greaterThan(0));
    gate.complete();
    await answering;
    s = c.read(centerControllerProvider);
    expect(s.message, '答错了，已收录进错题本；任务已提交，等待家长确认');
  });

  test('最后一题答错且提交失败：合并提示并可重新提交', () async {
    final (c, _, tasks, ctl) = await lastQuestionPending();
    tasks.failSubmit = true;
    await ctl.answer(1, 'x');
    final s = c.read(centerControllerProvider);
    expect(s.message, '答错了，已收录进错题本；提交任务失败，请稍后重试');
    expect(s.submitFailed, isTrue);
  });

  test('最后一题答错且收录失败、提交成功：合并提示', () async {
    final (c, center, _, ctl) = await lastQuestionPending();
    center.failWrong = true;
    await ctl.answer(1, 'x');
    expect(c.read(centerControllerProvider).message, '答错了（收录错题本失败，请稍后重试）；任务已提交，等待家长确认');
  });

  test('旧任务提交失败时提示回首页重新开始该任务', () async {
    final (c, _, tasks, ctl) = await lastQuestionPending();
    final gate = tasks.submitGate = Completer<void>();
    tasks.failSubmit = true;
    final first = ctl.answer(1, 'A2');
    ctl.openForTask(86, CenterTab.reading);
    gate.complete();
    await first;
    final s = c.read(centerControllerProvider);
    expect(s.message, '提交任务失败，请回首页重新开始该任务');
    expect(s.submitFailed, isFalse);
    expect(s.pending?.taskId, 86);
  });
}
