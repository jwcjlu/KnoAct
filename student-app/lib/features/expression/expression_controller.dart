import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../auth/session.dart';
import 'data/expression_repository.dart';

class ProbeTurn {
  const ProbeTurn({required this.q, required this.a});

  final String q;
  final String a;

  Map<String, String> toJson() => {'q': q, 'a': a};
}

class ExpressionState {
  const ExpressionState({
    this.topics = const [],
    this.selected,
    this.text = '',
    this.busy = false,
    this.done = false,
    this.error,
    this.submitError,
    this.probeOpen = false,
    this.probeTurns = const [],
    this.probeQuestion = '',
    this.probeError,
    this.probeBusy = false,
    this.probeDone = false,
  });

  final List<ExpressionTopic> topics;
  final ExpressionTopic? selected;
  final String text;
  final bool busy;
  final bool done;

  /// `forbidden`：功能未对该用户开放（如 403）；`failed`：加载失败。
  final String? error;

  /// `failed`：保存失败（与 [error] 加载失败分开）。
  final String? submitError;

  final bool probeOpen;
  final List<ProbeTurn> probeTurns;
  final String probeQuestion;
  final String? probeError;
  final bool probeBusy;
  final bool probeDone;

  ExpressionState copyWith({
    List<ExpressionTopic>? topics,
    ExpressionTopic? Function()? selected,
    String? text,
    bool? busy,
    bool? done,
    String? Function()? error,
    String? Function()? submitError,
    bool? probeOpen,
    List<ProbeTurn>? probeTurns,
    String? probeQuestion,
    String? Function()? probeError,
    bool? probeBusy,
    bool? probeDone,
  }) => ExpressionState(
    topics: topics ?? this.topics,
    selected: selected != null ? selected() : this.selected,
    text: text ?? this.text,
    busy: busy ?? this.busy,
    done: done ?? this.done,
    error: error != null ? error() : this.error,
    submitError: submitError != null ? submitError() : this.submitError,
    probeOpen: probeOpen ?? this.probeOpen,
    probeTurns: probeTurns ?? this.probeTurns,
    probeQuestion: probeQuestion ?? this.probeQuestion,
    probeError: probeError != null ? probeError() : this.probeError,
    probeBusy: probeBusy ?? this.probeBusy,
    probeDone: probeDone ?? this.probeDone,
  );
}

class ExpressionController extends Notifier<ExpressionState> {
  int _loadToken = 0;

  int? get _uid => ref.read(currentChildIdProvider);

  @override
  ExpressionState build() {
    ref.watch(currentChildIdProvider);
    _loadToken++;
    return const ExpressionState();
  }

  Future<void> loadTopics() async {
    final uid = _uid;
    if (uid == null || state.busy) return;
    final token = ++_loadToken;
    state = state.copyWith(busy: true);
    List<ExpressionTopic>? topics;
    String? loadError;
    try {
      topics = await ref.read(expressionRepositoryProvider).topics(userId: uid);
      loadError = null;
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        topics = const [];
        loadError = 'forbidden';
      } else {
        topics = null;
        loadError = 'failed';
      }
    } catch (_) {
      topics = null;
      loadError = 'failed';
    }
    if (!ref.mounted || token != _loadToken || _uid != uid) return;
    state = state.copyWith(
      topics: topics ?? state.topics,
      busy: false,
      error: () => loadError,
    );
  }

  void select(ExpressionTopic topic) {
    state = state.copyWith(selected: () => topic, done: false);
  }

  void setText(String value) {
    state = state.copyWith(text: value, done: false);
  }

  Future<void> openProbe() async {
    final uid = _uid;
    final topic = state.selected;
    final text = state.text.trim();
    if (uid == null || topic == null || text.isEmpty || state.probeBusy) return;

    state = state.copyWith(
      probeOpen: true,
      probeBusy: true,
      probeTurns: const [],
      probeQuestion: '',
      probeError: () => null,
      probeDone: false,
    );

    try {
      final result = await ref
          .read(expressionRepositoryProvider)
          .probe(
            userId: uid,
            knowledgePointId: topic.kind == 'knowledge_point' ? topic.id : null,
            itemId: topic.kind == 'training_item' ? topic.id : null,
            text: text,
            turns: const [],
          );
      if (!ref.mounted || _uid != uid) return;
      if (result.error != null) {
        state = state.copyWith(
          probeBusy: false,
          probeError: () => result.error,
        );
        return;
      }
      if (result.done) {
        state = state.copyWith(
          probeBusy: false,
          probeDone: true,
          probeQuestion: '',
        );
      } else {
        state = state.copyWith(
          probeBusy: false,
          probeQuestion: result.question,
        );
      }
    } catch (_) {
      if (ref.mounted && _uid == uid) {
        state = state.copyWith(
          probeBusy: false,
          probeError: () => 'unavailable',
        );
      }
    }
  }

  Future<void> answerProbe(String a) async {
    final q = state.probeQuestion;
    if (q.isEmpty) return;

    final uid = _uid;
    final topic = state.selected;
    final text = state.text.trim();
    if (uid == null || topic == null) return;

    final turns = [...state.probeTurns, ProbeTurn(q: q, a: a)];
    state = state.copyWith(probeTurns: turns, probeQuestion: '');

    if (turns.length >= 3) {
      state = state.copyWith(probeDone: true);
      return;
    }

    state = state.copyWith(probeBusy: true, probeError: () => null);
    try {
      final result = await ref
          .read(expressionRepositoryProvider)
          .probe(
            userId: uid,
            knowledgePointId: topic.kind == 'knowledge_point' ? topic.id : null,
            itemId: topic.kind == 'training_item' ? topic.id : null,
            text: text,
            turns: turns.map((t) => t.toJson()).toList(),
          );
      if (!ref.mounted || _uid != uid) return;
      if (result.error != null) {
        state = state.copyWith(
          probeBusy: false,
          probeError: () => result.error,
        );
        return;
      }
      if (result.done) {
        state = state.copyWith(
          probeBusy: false,
          probeDone: true,
          probeQuestion: '',
        );
      } else {
        state = state.copyWith(
          probeBusy: false,
          probeQuestion: result.question,
        );
      }
    } catch (_) {
      if (ref.mounted && _uid == uid) {
        state = state.copyWith(
          probeBusy: false,
          probeError: () => 'unavailable',
        );
      }
    }
  }

  Future<void> submit() async {
    final uid = _uid;
    final topic = state.selected;
    final text = state.text.trim();
    if (uid == null || topic == null || text.isEmpty || state.busy) return;

    final probeMaps = state.probeTurns.isEmpty
        ? null
        : state.probeTurns.map((t) => t.toJson()).toList();

    state = state.copyWith(busy: true, submitError: () => null);
    try {
      await ref
          .read(expressionRepositoryProvider)
          .createNote(
            userId: uid,
            knowledgePointId: topic.kind == 'knowledge_point' ? topic.id : null,
            itemId: topic.kind == 'training_item' ? topic.id : null,
            text: text,
            probeTurns: probeMaps,
          );
    } catch (_) {
      if (ref.mounted && _uid == uid) {
        state = state.copyWith(busy: false, submitError: () => 'failed');
      }
      return;
    }
    if (!ref.mounted || _uid != uid) return;
    state = state.copyWith(
      busy: false,
      done: true,
      text: text,
      submitError: () => null,
    );
  }

  void again() {
    state = ExpressionState(topics: state.topics);
  }
}

final expressionControllerProvider =
    NotifierProvider<ExpressionController, ExpressionState>(
      ExpressionController.new,
    );