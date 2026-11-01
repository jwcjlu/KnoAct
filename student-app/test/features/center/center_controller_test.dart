import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';

class FakeCenterRepository implements CenterRepository {
  CenterMaterial readingMaterial = const CenterMaterial(text: '课文', questions: [CenterQuestion('Q1', 'A1'), CenterQuestion('Q2', 'A2')]);
  CenterMaterial listeningMaterial = const CenterMaterial(text: 'Hi', questions: [CenterQuestion('L1', 'yes')]);
  final wrong = <String>[];

  @override
  Future<CenterMaterial> listening(int userId) async => listeningMaterial;

  @override
  Future<CenterMaterial> reading(int userId) async => readingMaterial;

  @override
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {
    wrong.add('$sourceType:$question:$yourAnswer');
  }
}

class FakeTaskRepository implements HomeRepository {
  final submitted = <int>[];

  @override
  Future<void> submitTask(int taskId) async => submitted.add(taskId);

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) => throw UnimplementedError();
  @override
  Future<List<StudyTask>> tasks(int userId, String date) => throw UnimplementedError();
  @override
  Future<int> balance(int userId) => throw UnimplementedError();
  @override
  Future<bool> redeem(int userId, String device, int minutes) => throw UnimplementedError();
}

Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository)> setup() async {
  SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
  final center = FakeCenterRepository();
  final tasks = FakeTaskRepository();
  final c = ProviderContainer(
    overrides: [
      centerRepositoryProvider.overrideWithValue(center),
      homeRepositoryProvider.overrideWithValue(tasks),
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
}
