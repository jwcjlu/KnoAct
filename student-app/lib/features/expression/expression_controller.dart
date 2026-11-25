import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../auth/session.dart';
import 'data/expression_repository.dart';

class ExpressionState {
  const ExpressionState({
    this.topics = const [],
    this.selected,
    this.text = '',
    this.busy = false,
    this.done = false,
    this.error,
  });

  final List<ExpressionTopic> topics;
  final ExpressionTopic? selected;
  final String text;
  final bool busy;
  final bool done;

  /// `forbidden`：功能未对该用户开放（如 403）；`failed`：加载失败。
  final String? error;

  ExpressionState copyWith({
    List<ExpressionTopic>? topics,
    ExpressionTopic? Function()? selected,
    String? text,
    bool? busy,
    bool? done,
    String? Function()? error,
  }) => ExpressionState(
    topics: topics ?? this.topics,
    selected: selected != null ? selected() : this.selected,
    text: text ?? this.text,
    busy: busy ?? this.busy,
    done: done ?? this.done,
    error: error != null ? error() : this.error,
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

  Future<void> submit() async {
    final uid = _uid;
    final topic = state.selected;
    final text = state.text.trim();
    if (uid == null || topic == null || text.isEmpty || state.busy) return;

    state = state.copyWith(busy: true);
    try {
      await ref
          .read(expressionRepositoryProvider)
          .createNote(
            userId: uid,
            knowledgePointId: topic.kind == 'knowledge_point' ? topic.id : null,
            itemId: topic.kind == 'training_item' ? topic.id : null,
            text: text,
          );
    } catch (_) {
      if (ref.mounted && _uid == uid) {
        state = state.copyWith(busy: false);
      }
      return;
    }
    if (!ref.mounted || _uid != uid) return;
    state = state.copyWith(busy: false, done: true, text: text);
  }

  void again() {
    state = ExpressionState(topics: state.topics);
  }
}

final expressionControllerProvider =
    NotifierProvider<ExpressionController, ExpressionState>(
      ExpressionController.new,
    );
