import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../home/data/home_repository.dart';
import 'data/bank_models.dart';
import 'data/bank_repository.dart';

class BankExerciseState {
  const BankExerciseState({
    this.bankId,
    this.taskId,
    this.loading = false,
    this.busy = false,
    this.questions = const [],
    this.selectedSingle = const {},
    this.selectedMulti = const {},
    this.blanks = const {},
    this.texts = const {},
    this.submitted = false,
    this.result,
    this.error,
  });

  final int? bankId;
  final int? taskId;
  final bool loading;
  final bool busy;
  final List<BankQuestion> questions;
  final Map<int, int> selectedSingle;
  final Map<int, List<int>> selectedMulti;
  final Map<int, List<String>> blanks;
  final Map<int, String> texts;
  final bool submitted;
  final BankSubmitResult? result;
  final String? error;

  BankExerciseState copyWith({
    int? bankId,
    int? taskId,
    bool? loading,
    bool? busy,
    List<BankQuestion>? questions,
    Map<int, int>? selectedSingle,
    Map<int, List<int>>? selectedMulti,
    Map<int, List<String>>? blanks,
    Map<int, String>? texts,
    bool? submitted,
    BankSubmitResult? result,
    String? error,
  }) {
    return BankExerciseState(
      bankId: bankId ?? this.bankId,
      taskId: taskId ?? this.taskId,
      loading: loading ?? this.loading,
      busy: busy ?? this.busy,
      questions: questions ?? this.questions,
      selectedSingle: selectedSingle ?? this.selectedSingle,
      selectedMulti: selectedMulti ?? this.selectedMulti,
      blanks: blanks ?? this.blanks,
      texts: texts ?? this.texts,
      submitted: submitted ?? this.submitted,
      result: result ?? this.result,
      error: error,
    );
  }
}

class BankExerciseController extends Notifier<BankExerciseState> {
  late BankRepository _repo;

  @override
  BankExerciseState build() {
    _repo = ref.read(bankRepositoryProvider);
    return const BankExerciseState();
  }

  Future<void> load(int bankId, {List<int>? questionIds, int? taskId}) async {
    state = state.copyWith(
      bankId: bankId,
      taskId: taskId,
      loading: true,
      error: null,
      submitted: false,
      result: null,
    );
    try {
      final qs = await _repo.fetchQuestions(bankId, questionIds: questionIds);
      state = state.copyWith(loading: false, questions: qs);
    } catch (e) {
      state = state.copyWith(loading: false, error: '加载题目失败');
    }
  }

  void setSingle(int qid, int value) {
    state = state.copyWith(selectedSingle: {...state.selectedSingle, qid: value});
  }

  void toggleMulti(int qid, int value, bool on) {
    final cur = <int>[...(state.selectedMulti[qid] ?? const <int>[])];
    if (on) {
      if (!cur.contains(value)) cur.add(value);
    } else {
      cur.remove(value);
    }
    state = state.copyWith(selectedMulti: {...state.selectedMulti, qid: cur});
  }

  void setBlank(int qid, int index, String text) {
    final q = state.questions.firstWhere((x) => x.id == qid, orElse: () => const BankQuestion(id: 0, qtype: '', qtypeCategory: '', question: '', options: []));
    final n = q.qtypeCategory == 'blank' ? 1 : 1;
    final list = List<String>.from(state.blanks[qid] ?? List.filled(n, ''));
    while (list.length <= index) {
      list.add('');
    }
    list[index] = text;
    state = state.copyWith(blanks: {...state.blanks, qid: list});
  }

  void setText(int qid, String text) {
    state = state.copyWith(texts: {...state.texts, qid: text});
  }

  Map<String, dynamic> _answerPayload(BankQuestion q) {
    if (q.qtypeCategory == 'choice') {
      if (q.qtype == 'multi_choice') {
        return {'question_id': q.id, 'selected_index': state.selectedMulti[q.id] ?? []};
      }
      return {'question_id': q.id, 'selected_index': state.selectedSingle[q.id] ?? 0};
    }
    if (q.qtypeCategory == 'blank') {
      final b = state.blanks[q.id] ?? [''];
      return {'question_id': q.id, 'blanks': b};
    }
    return {'question_id': q.id, 'text': state.texts[q.id] ?? ''};
  }

  Future<void> submit() async {
    final bankId = state.bankId;
    if (bankId == null || state.busy) return;
    state = state.copyWith(busy: true, error: null);
    try {
      final answers = state.questions.map(_answerPayload).toList();
      final result = await _repo.submit(bankId: bankId, answers: answers);
      final taskId = state.taskId;
      if (taskId != null) {
        await ref.read(homeRepositoryProvider).submitTask(taskId);
      }
      state = state.copyWith(busy: false, submitted: true, result: result);
    } catch (e) {
      state = state.copyWith(busy: false, error: '提交失败');
    }
  }
}

final bankExerciseControllerProvider =
    NotifierProvider<BankExerciseController, BankExerciseState>(BankExerciseController.new);
