import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import 'center_logic.dart';
import 'data/center_models.dart';
import 'data/center_repository.dart';

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
  final String? message;
  final int messageSeq;

  CenterState copyWith({
    CenterTab? tab,
    AsyncValue<CenterMaterial>? material,
    List<String>? inputs,
    List<bool?>? results,
    PendingTask? Function()? pending,
    bool? submitting,
  }) =>
      CenterState(
        tab: tab ?? this.tab,
        material: material ?? this.material,
        inputs: inputs ?? this.inputs,
        results: results ?? this.results,
        pending: pending != null ? pending() : this.pending,
        submitting: submitting ?? this.submitting,
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
        message: text,
        messageSeq: messageSeq + 1,
      );
}

class CenterController extends Notifier<CenterState> {
  int _loadToken = 0;

  @override
  CenterState build() => const CenterState();

  /// 首页点阅读/听力任务时调用，随后跳转到学习中心
  void openForTask(int taskId, CenterTab tab) {
    state = state.copyWith(tab: tab, pending: () => PendingTask(taskId, tab));
  }

  /// 进入学习中心：重新拉取当前 Tab 材料并清空作答
  Future<void> enter() => _load(state.tab);

  void leave() {
    state = state.copyWith(pending: () => null);
  }

  Future<void> selectTab(CenterTab tab) {
    if (state.pending != null && state.pending!.tab != tab) {
      state = state.copyWith(pending: () => null);
    }
    return _load(tab);
  }

  Future<void> reload() => _load(state.tab);

  Future<void> _load(CenterTab tab) async {
    final token = ++_loadToken;
    state = state.copyWith(tab: tab, material: const AsyncLoading(), inputs: const [], results: const []);
    final uid = ref.read(currentChildIdProvider);
    final repo = ref.read(centerRepositoryProvider);
    final result = await AsyncValue.guard(
      () => tab == CenterTab.listening ? repo.listening(uid) : repo.reading(uid),
    );
    if (token != _loadToken) return;
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
    final inputs = [...state.inputs];
    inputs[index] = value;
    state = state.copyWith(inputs: inputs);
  }

  Future<void> answer(int index, String input) async {
    final m = state.material.value;
    if (m == null || index >= m.questions.length || state.results[index] != null) return;
    final q = m.questions[index];
    final ok = isCorrectAnswer(input, q.answer);
    final results = [...state.results]..[index] = ok;
    final inputs = [...state.inputs]..[index] = input;
    state = state.copyWith(results: results, inputs: inputs);
    if (ok) {
      state = state.withMessage('回答正确！');
    } else {
      try {
        await ref.read(centerRepositoryProvider).submitWrong(
              userId: ref.read(currentChildIdProvider),
              question: q.question,
              yourAnswer: input,
              correctAnswer: q.answer,
              sourceType: state.tab.sourceType,
            );
        state = state.withMessage('答错了，已收录进错题本');
      } catch (_) {
        state = state.withMessage('答错了（收录错题本失败，请稍后重试）');
      }
    }
    await _maybeSubmitTask();
  }

  Future<void> _maybeSubmitTask() async {
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
      return;
    }
    state = state.copyWith(submitting: true);
    try {
      await ref.read(homeRepositoryProvider).submitTask(pending!.taskId);
      state = state.copyWith(pending: () => null, submitting: false).withMessage('已提交，等待家长确认');
    } catch (_) {
      state = state.copyWith(submitting: false).withMessage('提交任务失败，请稍后重试');
    }
  }
}

final centerControllerProvider = NotifierProvider<CenterController, CenterState>(CenterController.new);
