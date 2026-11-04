import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'data/knowledge_repository.dart';

class KnowledgeState {
  const KnowledgeState({
    this.taskId,
    this.title = '',
    this.points = const [],
    this.inputs = const [],
    this.results = const [],
    this.busy = false,
  });

  final int? taskId;
  final String title;
  final List<KnowledgePoint> points;
  final List<String> inputs;

  /// 逐题判分结果（null=未判分，对齐 points 下标）
  final List<bool?> results;
  final bool busy;

  KnowledgeState copyWith({
    int? taskId,
    String? title,
    List<KnowledgePoint>? points,
    List<String>? inputs,
    List<bool?>? results,
    bool? busy,
  }) =>
      KnowledgeState(
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        points: points ?? this.points,
        inputs: inputs ?? this.inputs,
        results: results ?? this.results,
        busy: busy ?? this.busy,
      );
}

class KnowledgeController extends Notifier<KnowledgeState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  KnowledgeState build() {
    ref.watch(currentChildIdProvider);
    return const KnowledgeState();
  }

  void init({required int taskId, required String title, required String content}) {
    final points = parseKnowledgeContent(content);
    state = KnowledgeState(
      taskId: taskId,
      title: title,
      points: points,
      inputs: List.filled(points.length, ''),
      results: List<bool?>.filled(points.length, null),
    );
  }

  void setInput(int index, String value) {
    if (index < 0 || index >= state.inputs.length) return;
    final inputs = [...state.inputs];
    inputs[index] = value;
    state = state.copyWith(inputs: inputs);
  }

  Future<void> submit() async {
    final uid = _uid;
    final taskId = state.taskId;
    if (uid == null || taskId == null || state.busy) return;
    if (state.inputs.any((i) => i.trim().isEmpty)) return;

    state = state.copyWith(busy: true);
    KnowledgeGradeResult? result;
    try {
      result = await ref.read(knowledgeRepositoryProvider).grade(
            userId: uid,
            taskId: taskId,
            answers: [
              for (var i = 0; i < state.points.length; i++)
                {'id': state.points[i].id, 'user_answer': state.inputs[i].trim()},
            ],
          );
      // 判分后提交任务（待家长确认）
      await ref.read(homeRepositoryProvider).submitTask(taskId);
    } catch (_) {
      result = null;
    }
    if (!ref.mounted || _uid != uid) return;

    if (result != null) {
      // 结果按 id 映射回 points 下标
      final byId = {for (final r in result.items) r.id: r.isCorrect};
      final results = [
        for (final p in state.points) byId.containsKey(p.id) ? byId[p.id] : null,
      ];
      state = state.copyWith(busy: false, results: results);
      try {
        ref.read(homeControllerProvider.notifier).reload();
      } catch (_) {}
    } else {
      state = state.copyWith(busy: false);
    }
  }
}

final knowledgeControllerProvider = NotifierProvider<KnowledgeController, KnowledgeState>(KnowledgeController.new);
