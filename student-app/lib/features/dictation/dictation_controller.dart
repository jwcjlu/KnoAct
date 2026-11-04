import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'data/dictation_repository.dart';

/// 单个词的听写状态
class DictWordResult {
  const DictWordResult({required this.word, required this.written, required this.isCorrect, this.appealed = false});

  final DictWord word;
  final String written;
  final bool isCorrect;
  final bool appealed;
}

class DictationState {
  const DictationState({
    this.taskId,
    this.title = '',
    this.subject = '语文',
    this.words = const [],
    this.currentIndex = 0,
    this.busy = false,
    this.results = const [],
    this.done = false,
  });

  final int? taskId;
  final String title;
  final String subject;
  final List<DictWord> words;
  final int currentIndex;
  final bool busy;

  /// 已批改的结果（按 words 下标对齐）
  final List<DictWordResult?> results;
  final bool done;

  bool get isEnglish => subject == '英语';

  DictationState copyWith({
    int? taskId,
    String? title,
    String? subject,
    List<DictWord>? words,
    int? currentIndex,
    bool? busy,
    List<DictWordResult?>? results,
    bool? done,
  }) =>
      DictationState(
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        subject: subject ?? this.subject,
        words: words ?? this.words,
        currentIndex: currentIndex ?? this.currentIndex,
        busy: busy ?? this.busy,
        results: results ?? this.results,
        done: done ?? this.done,
      );
}

class DictationController extends Notifier<DictationState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  DictationState build() {
    ref.watch(currentChildIdProvider);
    return const DictationState();
  }

  /// 从首页任务进入：解析 content 为词条
  void init({required int taskId, required String title, required String subject, required String content}) {
    final words = parseDictContent(content);
    state = DictationState(
      taskId: taskId,
      title: title,
      subject: subject,
      words: words,
      results: List<DictWordResult?>.filled(words.length, null),
    );
  }

  /// 提交当前词的手写图批改
  Future<void> submitHandwriting(String imageBase64) async {
    final uid = _uid;
    if (uid == null || state.busy || state.done) return;
    final index = state.currentIndex;
    if (index >= state.words.length) return;
    final word = state.words[index];

    state = state.copyWith(busy: true);
    List<DictGradeItem> items;
    try {
      items = await ref.read(dictationRepositoryProvider).gradeHandwriting(
            userId: uid,
            words: [{'index': 0, 'word': word.word}],
            imageBase64: imageBase64,
          );
    } catch (_) {
      items = const [];
    }
    if (!ref.mounted || _uid != uid) return;

    final item = items.isNotEmpty ? items.first : null;
    final results = [...state.results];
    results[index] = DictWordResult(
      word: word,
      written: item?.written ?? '',
      isCorrect: item?.isCorrect ?? false,
    );
    state = state.copyWith(busy: false, results: results);
  }

  /// 进入下一个词；已是最后一个词时完成
  Future<void> next() async {
    final index = state.currentIndex;
    if (index + 1 < state.words.length) {
      state = state.copyWith(currentIndex: index + 1);
    } else {
      await _finish();
    }
  }

  Future<void> _finish() async {
    final uid = _uid;
    if (uid == null || state.done) return;
    final results = state.results.whereType<DictWordResult>().toList();
    final correct = results.where((r) => r.isCorrect).length;
    final wrong = results.where((r) => !r.isCorrect).toList();
    try {
      await ref.read(dictationRepositoryProvider).complete(
            userId: uid,
            correct: correct,
            wrong: wrong.length,
            wrongWords: [
              for (final r in wrong) {'word': r.word.word, 'your_answer': r.written, 'word_id': r.word.id},
            ],
          );
      // 提交任务（待家长确认）
      final taskId = state.taskId;
      if (taskId != null) {
        await ref.read(homeRepositoryProvider).submitTask(taskId);
      }
    } catch (_) {
      // 完成接口失败仍标记 done，避免卡住
    }
    if (!ref.mounted) return;
    state = state.copyWith(done: true);
    try {
      ref.read(homeControllerProvider.notifier).reload();
    } catch (_) {}
  }

  Future<void> appeal(int index) async {
    final uid = _uid;
    final r = state.results[index];
    if (uid == null || r == null) return;
    try {
      await ref.read(dictationRepositoryProvider).appeal(userId: uid, word: r.word.word, wordId: r.word.id);
    } catch (_) {}
  }
}

final dictationControllerProvider = NotifierProvider<DictationController, DictationState>(DictationController.new);
