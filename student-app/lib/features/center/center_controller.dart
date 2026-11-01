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

  /// 首页点阅读/听力任务时调用，随后跳转到学习中心
  void openForTask(int taskId, CenterTab tab) {
    _loadToken++;
    state = state.copyWith(
      tab: tab,
      material: const AsyncLoading(),
      inputs: const [],
      results: const [],
      pending: () => PendingTask(taskId, tab),
      submitFailed: false,
    );
  }

  /// 进入学习中心：重新拉取当前 Tab 材料并清空作答
  Future<void> enter() => _load(state.tab);

  void leave() {
    state = state.copyWith(pending: () => null, submitFailed: false);
    unawaited(ref.read(speechPlayerProvider).stop());
  }

  Future<void> selectTab(CenterTab tab) {
    if (state.pending != null && state.pending!.tab != tab) {
      state = state.copyWith(pending: () => null, submitFailed: false);
    }
    if (tab == CenterTab.reading) unawaited(ref.read(speechPlayerProvider).stop());
    return _load(tab);
  }

  Future<void> reload() => _load(state.tab);

  Future<void> retrySubmit() => _submitAndReport();

  Future<void> _load(CenterTab tab) async {
    final uid = _uid;
    if (uid == null) return;
    // 先读写 state（可能触发换孩子后的 build 并自增 _loadToken），再取本次 token
    state = state.copyWith(tab: tab, material: const AsyncLoading(), inputs: const [], results: const [], submitFailed: false);
    final token = ++_loadToken;
    final repo = ref.read(centerRepositoryProvider);
    final result = await AsyncValue.guard(
      () => tab == CenterTab.listening ? repo.listening(uid) : repo.reading(uid),
    );
    if (_stale(token, uid)) return;
    final count = result.value?.questions.length ?? 0;
    state = state.copyWith(
      material: result,
      inputs: List.filled(count, ''),
      results: List<bool?>.filled(count, null),
    );
    final m = result.value;
    if (m != null && m.isEmpty && state.pending?.tab == tab) {
      state = state.withMessage('暂无材料，暂时无法完成该任务');
    }
  }

  void setInput(int index, String value) {
    if (index < 0 || index >= state.inputs.length) return;
    final inputs = [...state.inputs];
    inputs[index] = value;
    state = state.copyWith(inputs: inputs);
  }

  Future<void> answer(int index, String input) async {
    final uid = _uid;
    final m = state.material.value;
    if (uid == null || m == null || index >= m.questions.length || state.results[index] != null) return;
    final q = m.questions[index];
    final ok = isCorrectAnswer(input, q.answer);
    final results = [...state.results]..[index] = ok;
    final inputs = [...state.inputs]..[index] = input;
    state = state.copyWith(results: results, inputs: inputs);
    if (ok) state = state.withMessage('回答正确！');
    // 与错题收录同时发起提交：收录期间离开/切 Tab 不能清掉已完成任务的提交
    await _submitAndReport(wrong: ok ? null : _recordWrong(q, input, uid));
  }

  /// 返回提示文案；结果已过期（切 Tab / 换孩子）时返回 null
  Future<String?> _recordWrong(CenterQuestion q, String input, int uid) async {
    final token = _loadToken;
    String msg;
    try {
      await ref.read(centerRepositoryProvider).submitWrong(
            userId: uid,
            question: q.question,
            yourAnswer: input,
            correctAnswer: q.answer,
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
