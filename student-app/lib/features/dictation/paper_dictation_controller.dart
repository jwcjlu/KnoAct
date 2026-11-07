import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'data/dictation_repository.dart';
enum PaperDictationPhase { listen, upload, grading, result, rewrite, finishGate, done }

class PaperWrongWord {
  const PaperWrongWord({
    required this.word,
    required this.id,
    required this.pinyin,
    required this.meaning,
    this.yours = '',
    this.written = '',
  });

  final String word;
  final int id;
  final String pinyin;
  final String meaning;
  final String yours;
  final String written;

  PaperWrongWord copyWith({String? yours, String? written}) => PaperWrongWord(
        word: word,
        id: id,
        pinyin: pinyin,
        meaning: meaning,
        yours: yours ?? this.yours,
        written: written ?? this.written,
      );
}

class PaperDictationState {
  const PaperDictationState({
    this.taskId,
    this.title = '',
    this.subject = '语文',
    this.words = const [],
    this.phase = PaperDictationPhase.listen,
    this.idx = 0,
    this.rewriteIdx = 0,
    this.rewriting = false,
    this.hints = const {},
    this.busy = false,
    this.gradeImageBase64 = '',
    this.wrong = const [],
    this.firstRoundWrong = const [],
    this.correct = 0,
    this.gradeResults = const [],
    this.dictationCompleted = false,
  });

  final int? taskId;
  final String title;
  final String subject;
  final List<DictWord> words;
  final PaperDictationPhase phase;
  final int idx;
  final int rewriteIdx;
  final bool rewriting;
  final Map<int, String> hints;
  final bool busy;
  final String gradeImageBase64;
  final List<PaperWrongWord> wrong;
  final List<PaperWrongWord> firstRoundWrong;
  final int correct;
  final List<DictGradeItem> gradeResults;
  final bool dictationCompleted;

  bool get isEnglish => subject == '英语';

  PaperDictationState copyWith({
    int? taskId,
    String? title,
    String? subject,
    List<DictWord>? words,
    PaperDictationPhase? phase,
    int? idx,
    int? rewriteIdx,
    bool? rewriting,
    Map<int, String>? hints,
    bool? busy,
    String? gradeImageBase64,
    List<PaperWrongWord>? wrong,
    List<PaperWrongWord>? firstRoundWrong,
    int? correct,
    List<DictGradeItem>? gradeResults,
    bool? dictationCompleted,
  }) =>
      PaperDictationState(
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        subject: subject ?? this.subject,
        words: words ?? this.words,
        phase: phase ?? this.phase,
        idx: idx ?? this.idx,
        rewriteIdx: rewriteIdx ?? this.rewriteIdx,
        rewriting: rewriting ?? this.rewriting,
        hints: hints ?? this.hints,
        busy: busy ?? this.busy,
        gradeImageBase64: gradeImageBase64 ?? this.gradeImageBase64,
        wrong: wrong ?? this.wrong,
        firstRoundWrong: firstRoundWrong ?? this.firstRoundWrong,
        correct: correct ?? this.correct,
        gradeResults: gradeResults ?? this.gradeResults,
        dictationCompleted: dictationCompleted ?? this.dictationCompleted,
      );
}

class PaperDictationController extends Notifier<PaperDictationState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  PaperDictationState build() {
    ref.watch(currentChildIdProvider);
    return const PaperDictationState();
  }

  void bootstrap({
    required int? taskId,
    required String title,
    required String subject,
    required List<DictWord> words,
  }) {
    state = PaperDictationState(
      taskId: taskId,
      title: title,
      subject: subject,
      words: words,
    );
  }

  int get _hintKey => state.rewriting ? state.rewriteIdx : state.idx;

  DictWord? get _currentWord {
    if (state.rewriting) {
      if (state.rewriteIdx >= state.wrong.length) return null;
      final w = state.wrong[state.rewriteIdx];
      return DictWord(id: w.id, word: w.word, extra: '${w.pinyin} ${w.meaning}'.trim());
    }
    if (state.idx >= state.words.length) return null;
    return state.words[state.idx];
  }

  String? speakText() => _currentWord?.word;

  void hint() {
    final key = _hintKey;
    final hints = Map<int, String>.from(state.hints);
    if (state.isEnglish) {
      hints[key] = 'meaning';
    } else if (hints[key] != 'pinyin') {
      hints[key] = 'pinyin';
    } else {
      hints[key] = 'meaning';
    }
    state = state.copyWith(hints: hints);
  }

  String? hintText() {
    final key = _hintKey;
    final level = state.hints[key];
    final w = _currentWord;
    if (w == null || level == null) return null;
    if (state.isEnglish || level == 'meaning') return '提示：${w.meaning}';
    return '提示：${w.pinyin}';
  }

  void advanceListen() {
    if (state.rewriting) {
      var ri = state.rewriteIdx + 1;
      if (ri >= state.wrong.length) {
        state = state.copyWith(phase: PaperDictationPhase.upload, rewriteIdx: 0);
      } else {
        state = state.copyWith(rewriteIdx: ri);
      }
      return;
    }
    var i = state.idx + 1;
    if (i >= state.words.length) {
      state = state.copyWith(phase: PaperDictationPhase.upload, idx: i);
    } else {
      state = state.copyWith(idx: i);
    }
  }

  void beginGrading(String imageBase64) {
    state = state.copyWith(phase: PaperDictationPhase.grading, gradeImageBase64: imageBase64, busy: true);
  }

  List<Map<String, dynamic>> _gradeWordPayload() {
    if (state.rewriting) {
      return [
        for (var i = 0; i < state.wrong.length; i++) {'index': i, 'word': state.wrong[i].word},
      ];
    }
    return [
      for (var i = 0; i < state.words.length; i++) {'index': i, 'word': state.words[i].word},
    ];
  }

  Future<void> runGrading() async {
    final uid = _uid;
    if (uid == null || state.gradeImageBase64.isEmpty) return;
    try {
      final items = await ref.read(dictationRepositoryProvider).gradeHandwriting(
            userId: uid,
            words: _gradeWordPayload(),
            imageBase64: state.gradeImageBase64,
          );
      if (!ref.mounted) return;
      if (items.isEmpty) {
        state = state.copyWith(phase: PaperDictationPhase.upload, busy: false);
        return;
      }
      _applyGradeResults(items);
    } catch (_) {
      if (ref.mounted) state = state.copyWith(phase: PaperDictationPhase.upload, busy: false);
    }
  }

  @visibleForTesting
  void applyGradeResultsForTest(List<DictGradeItem> items) => _applyGradeResults(items);

  void _applyGradeResults(List<DictGradeItem> items) {
    if (state.rewriting) {
      final stillWrong = <PaperWrongWord>[];
      var correct = state.correct;
      for (var i = 0; i < state.wrong.length; i++) {
        final r = items.where((x) => x.index == i).firstOrNull;
        final keep = state.wrong[i];
        if (r != null && r.isCorrect) {
          correct++;
        } else {
          stillWrong.add(keep.copyWith(written: r?.written ?? '', yours: r?.written ?? keep.yours));
        }
      }
      if (stillWrong.isEmpty) {
        state = state.copyWith(
          wrong: const [],
          correct: correct,
          phase: PaperDictationPhase.finishGate,
          gradeResults: items,
          busy: false,
          rewriting: false,
        );
      } else {
        state = state.copyWith(
          wrong: stillWrong,
          correct: correct,
          phase: PaperDictationPhase.result,
          gradeResults: items,
          busy: false,
          rewriteIdx: 0,
        );
      }
      return;
    }

    var correct = 0;
    final wrong = <PaperWrongWord>[];
    final firstRoundWrong = <PaperWrongWord>[];
    for (var i = 0; i < state.words.length; i++) {
      final w = state.words[i];
      final r = items.where((x) => x.index == i).firstOrNull;
      if (r != null && r.isCorrect) {
        correct++;
      } else {
        final item = PaperWrongWord(
          word: w.word,
          id: w.id,
          pinyin: w.pinyin,
          meaning: w.meaning,
          yours: r?.written ?? '',
          written: r?.written ?? '',
        );
        wrong.add(item);
        firstRoundWrong.add(item);
      }
    }
    state = state.copyWith(
      correct: correct,
      wrong: wrong,
      firstRoundWrong: firstRoundWrong,
      gradeResults: items,
      phase: PaperDictationPhase.result,
      busy: false,
    );
  }

  void startRewrite() {
    if (state.wrong.isEmpty) {
      state = state.copyWith(phase: PaperDictationPhase.finishGate);
      return;
    }
    state = state.copyWith(
      rewriting: true,
      phase: PaperDictationPhase.rewrite,
      rewriteIdx: 0,
      hints: const {},
    );
  }

  void goFinishGate() {
    state = state.copyWith(phase: PaperDictationPhase.finishGate, rewriting: false);
  }

  Future<bool> completeDictation() async {
    if (state.dictationCompleted) return true;
    final uid = _uid;
    if (uid == null) return false;
    final wrongWords = [
      for (final w in (state.firstRoundWrong.isNotEmpty ? state.firstRoundWrong : state.wrong))
        {'word': w.word, 'your_answer': w.yours, 'word_id': w.id},
    ];
    try {
      await ref.read(dictationRepositoryProvider).complete(
            userId: uid,
            correct: state.correct,
            wrong: wrongWords.length,
            wrongWords: wrongWords,
          );
      state = state.copyWith(dictationCompleted: true);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// 上传打卡照（[bytes]）后提交任务；未传图则不调用 submit。
  Future<bool> finishCheckIn({required List<int> bytes, String filename = 'dictation.jpg'}) async {
    final taskId = state.taskId;
    if (taskId == null) {
      state = state.copyWith(phase: PaperDictationPhase.done);
      try {
        ref.read(homeControllerProvider.notifier).reload();
      } catch (_) {}
      return true;
    }
    state = state.copyWith(busy: true);
    try {
      await ref.read(homeRepositoryProvider).uploadTaskPhoto(taskId, bytes, filename: filename);
      await ref.read(homeRepositoryProvider).submitTask(taskId);
      state = state.copyWith(phase: PaperDictationPhase.done, busy: false);
      ref.read(homeControllerProvider.notifier).reload();
      return true;
    } catch (_) {
      state = state.copyWith(busy: false);
      return false;
    }
  }

  Future<void> appealWord(PaperWrongWord w) async {
    final uid = _uid;
    if (uid == null) return;
    try {
      await ref.read(dictationRepositoryProvider).appeal(userId: uid, word: w.word, wordId: w.id);
    } catch (_) {}
  }

  Uint8List? gradeImageBytes() {
    if (state.gradeImageBase64.isEmpty) return null;
    try {
      return base64Decode(state.gradeImageBase64);
    } catch (_) {
      return null;
    }
  }
}

final paperDictationControllerProvider =
    NotifierProvider<PaperDictationController, PaperDictationState>(PaperDictationController.new);
