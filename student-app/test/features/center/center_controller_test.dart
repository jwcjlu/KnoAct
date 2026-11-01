import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/center/speech_player.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';

class FakeCenterRepository implements CenterRepository {
  CenterMaterial readingMaterial = const CenterMaterial(text: '课文', questions: [CenterQuestion('Q1', 'A1'), CenterQuestion('Q2', 'A2')]);
  CenterMaterial listeningMaterial = const CenterMaterial(text: 'Hi', questions: [CenterQuestion('L1', 'yes')]);
  final wrong = <String>[];

  /// 非空时 submitWrong 等待它完成后才返回
  Completer<void>? wrongGate;

  @override
  Future<CenterMaterial> listening(int userId) async => listeningMaterial;

  @override
  Future<CenterMaterial> reading(int userId) async => readingMaterial;

  @override
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {
    wrong.add('$sourceType:$question:$yourAnswer');
    final gate = wrongGate;
    if (gate != null) await gate.future;
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
  Future<int> balance(int userId) => throw UnimplementedError();
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

Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository)> setup() async {
  SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
  final center = FakeCenterRepository();
  final tasks = FakeTaskRepository();
  speech = FakeSpeechPlayer();
  final c = ProviderContainer(
    overrides: [
      centerRepositoryProvider.overrideWithValue(center),
      homeRepositoryProvider.overrideWithValue(tasks),
      speechPlayerProvider.overrideWithValue(speech),
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
}
