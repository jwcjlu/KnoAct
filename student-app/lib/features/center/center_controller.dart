import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'center_logic.dart';
import 'data/center_models.dart';
import 'data/center_repository.dart';
import 'speech_player.dart';

class PendingTask {
  const PendingTask(this.taskId, this.tab);

  final int taskId;
  final CenterTab tab;
}

class CenterState {
  const CenterState({
    this.tab = CenterTab.listening,
    this.material = const AsyncLoading<CenterMaterial>(),
    this.inputs = const [],
    this.results = const [],
    this.pending,
    this.submitting = false,
    this.submitFailed = false,
    this.message,
    this.messageSeq = 0,
  });

  final CenterTab tab;
  final AsyncValue<CenterMaterial> material;
  final List<String> inputs;

  /// 每题作答结果：null 未作答，true/false 对错
  final List<bool?> results;
  final PendingTask? pending;
  final bool submitting;

  /// 当前待提交任务最近一次提交失败，界面据此显示「重新提交」
  final bool submitFailed;
  final String? message;
  final int messageSeq;

  CenterState copyWith({
    CenterTab? tab,
    AsyncValue<CenterMaterial>? material,
    List<String>? inputs,
    List<bool?>? results,
    PendingTask? Function()? pending,
    bool? submitting,
    bool? submitFailed,
  }) =>
      CenterState(
        tab: tab ?? this.tab,
        material: material ?? this.material,
        inputs: inputs ?? this.inputs,
        results: results ?? this.results,
        pending: pending != null ? pending() : this.pending,
        submitting: submitting ?? this.submitting,
        submitFailed: submitFailed ?? this.submitFailed,
        message: message,
        messageSeq: messageSeq,
      );

  CenterState withMessage(String text) => CenterState(
        tab: tab,
        material: material,
        inputs: inputs,
        results: results,
        pending: pending,
        submitting: submitting,
        submitFailed: submitFailed,
        message: text,
        messageSeq: messageSeq + 1,
      );
}

typedef _SubmitResult = ({int taskId, bool ok, bool current});

class CenterController extends Notifier<CenterState> {
  int _loadToken = 0;

  int? get _uid => ref.read(currentChildIdProvider);

  @override
  CenterState build() {
    // 换孩子（含退出登录）时重建：状态清空，上一个孩子的在途结果作废
    ref.watch(currentChildIdProvider);
    _loadToken++;
    final speech = ref.read(speechPlayerProvider);
    ref.onDispose(() => unawaited(speech.stop()));
    return const CenterState();
  }

  /// 请求返回时孩子已切换或材料已重新加载
  bool _stale(int token, int uid) => !ref.mounted || token != _loadToken || _uid != uid;

  /// 首页点英语听力任务时调用，随后跳转到学习中心作答
  void openForTask(int taskId) {
    _loadToken++;
    state = state.copyWith(
      tab: CenterTab.listening,
      material: const AsyncLoading(),
      inputs: const [],
      results: const [],
      pending: () => PendingTask(taskId, CenterTab.listening),
      submitFailed: false,
    );
  }

  /// 进入学习中心：仅有待提交听力任务时拉材料；否则展示阅读入口引导
  Future<void> enter() async {
    if (state.pending != null) {
      await _loadListening();
      return;
    }
    state = state.copyWith(
      tab: CenterTab.listening,
      material: const AsyncData(CenterMaterial.empty),
      inputs: const [],
      results: const [],
      submitFailed: false,
    );
  }

  void leave() {
    state = state.copyWith(pending: () => null, submitFailed: false);
    unawaited(ref.read(speechPlayerProvider).stop());
  }

  Future<void> reload() async {
    if (state.pending == null) return;
    await _loadListening();
  }

  Future<void> retrySubmit() => _submitAndReport();

  Future<void> _loadListening() async {
    final uid = _uid;
    if (uid == null) return;
    state = state.copyWith(
      tab: CenterTab.listening,
      material: const AsyncLoading(),
      inputs: const [],
      results: const [],
      submitFailed: false,
    );
    final token = ++_loadToken;
    final repo = ref.read(centerRepositoryProvider);
    final result = await AsyncValue.guard(() => repo.listening(uid));
    if (_stale(token, uid)) return;
    final count = result.value?.questions.length ?? 0;
    state = state.copyWith(
      material: result,
      inputs: List.filled(count, ''),
      results: List<bool?>.filled(count, null),
    );
    final m = result.value;
    if (m != null && m.isEmpty && state.pending != null) {
      state = state.withMessage('暂无材料，暂时无法完成该任务');
    }
  }

  void setInput(int index, String value) {
    if (index < 0 || index >= state.inputs.length) return;
    final inputs = [...state.inputs];
    inputs[index] = value;
    state = state.copyWith(inputs: inputs);
  }

  Future<void> answer(int index, {String? text, int? selectedIndex}) async {
    final uid = _uid;
    final m = state.material.value;
    if (uid == null || m == null || index >= m.questions.length || state.results[index] != null) return;
    final q = m.questions[index];
    final bool ok;
    final String stored;
    final String yourAnswer;
    final String correctAnswer;
    final mcListening = state.tab == CenterTab.listening && q.options.length >= 4;
    if ((q.isMultipleChoice || mcListening) && selectedIndex != null) {
      final ci = q.correctIndex ?? 0;
      if (ci < 0 || ci >= q.options.length) return;
      if (selectedIndex < 0 || selectedIndex >= q.options.length) return;
      ok = isCorrectListening(selectedIndex, ci);
      stored = q.options[selectedIndex];
      yourAnswer = stored;
      correctAnswer = q.options[ci];
    } else if (text != null) {
      ok = isCorrectAnswer(text, q.answer);
      stored = text;
      yourAnswer = text;
      correctAnswer = q.answer;
    } else {
      return;
    }
    final results = [...state.results]..[index] = ok;
    final inputs = [...state.inputs]..[index] = stored;
    state = state.copyWith(results: results, inputs: inputs);
    if (ok) state = state.withMessage('回答正确！');
    // 与错题收录同时发起提交：收录期间离开/切 Tab 不能清掉已完成任务的提交
    await _submitAndReport(wrong: ok ? null : _recordWrong(q, yourAnswer, correctAnswer, uid));
  }

  /// 返回提示文案；结果已过期（切 Tab / 换孩子）时返回 null
  Future<String?> _recordWrong(CenterQuestion q, String yourAnswer, String correctAnswer, int uid) async {
    final token = _loadToken;
    String msg;
    try {
      await ref.read(centerRepositoryProvider).submitWrong(
            userId: uid,
            question: q.question,
            yourAnswer: yourAnswer,
            correctAnswer: correctAnswer,
            sourceType: state.tab.sourceType,
          );
      msg = '答错了，已收录进错题本';
    } catch (_) {
      msg = '答错了（收录错题本失败，请稍后重试）';
    }
    return _stale(token, uid) ? null : msg;
  }

  /// 满足条件时提交待提交任务，再显示一条提示：最后一题答错时与 [wrong] 的收录结果合并
  Future<void> _submitAndReport({Future<String?>? wrong}) async {
    final uid = _uid;
    if (uid == null) return;
    final submit = await _submitPending(uid);
    final wrongMsg = wrong == null ? null : await wrong;
    if (!ref.mounted || _uid != uid) return;
    final submitMsg = switch (submit) {
      null => null,
      (ok: true, current: _, taskId: _) => wrong == null ? '已提交，等待家长确认' : '任务已提交，等待家长确认',
      (ok: false, current: true, taskId: _) => '提交任务失败，请稍后重试',
      (ok: false, current: false, taskId: _) => '提交任务失败，请回首页重新开始该任务',
    };
    final text = [?wrongMsg, ?submitMsg].join('；');
    if (text.isNotEmpty) state = state.withMessage(text);
    if (submit != null && state.pending != null && state.pending!.taskId != submit.taskId) await _submitAndReport();
  }

  /// 请求返回后立即更新提交状态并刷新首页；提示由调用方统一显示。未提交或已换孩子时返回 null
  Future<_SubmitResult?> _submitPending(int uid) async {
    final m = state.material.value;
    final pending = state.pending;
    final answered = state.results.where((r) => r != null).length;
    if (!shouldAutoSubmit(
      taskTab: pending?.tab,
      currentTab: state.tab,
      questionCount: m?.questions.length ?? 0,
      answeredCount: answered,
      submitting: state.submitting,
    )) {
      return null;
    }
    final taskId = pending!.taskId;
    state = state.copyWith(submitting: true, submitFailed: false);
    var ok = false;
    try {
      await ref.read(homeRepositoryProvider).submitTask(taskId);
      ok = true;
    } catch (_) {
      // 失败时保留待提交任务，交给「重新提交」
    }
    if (!ref.mounted || _uid != uid) return null;
    final current = state.pending?.taskId == taskId;
    state = state.copyWith(
      submitting: false,
      pending: ok && current ? () => null : null,
      submitFailed: !ok && current,
    );
    if (ok) {
      try {
        unawaited(ref.read(homeControllerProvider.notifier).reload());
      } catch (_) {
        // 首页刷新失败不影响提交结果
      }
    }
    return (taskId: taskId, ok: ok, current: current);
  }
}

final centerControllerProvider = NotifierProvider<CenterController, CenterState>(CenterController.new);
