import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import '../home/home_controller.dart';
import 'data/drill_repository.dart';

/// 会话阶段：引导 → 四步 → 复盘。
enum DrillPhase { intro, steps, review }

/// NPC 气泡：形象 emoji + 文案，答错/答对/引导时闪现。
class NpcMessage {
  const NpcMessage(this.emoji, this.text);
  final String emoji;
  final String text;
}

class DrillState {
  const DrillState({
    this.taskId,
    this.title = '',
    this.session,
    this.phase = DrillPhase.intro,
    this.stepIndex = 0,
    this.itemIndex = 0,
    this.npc,
    this.busy = false,
    this.stars = 0,
    this.completed = false,
    this.revealRule = false,
  });

  final int? taskId;
  final String title;
  final DrillSession? session;
  final DrillPhase phase;
  final int stepIndex; // 当前步在 steps 里的下标
  final int itemIndex; // 当前条目下标
  final NpcMessage? npc; // 当前气泡（null 不显示）
  final bool busy;
  final int stars;
  final bool completed;
  final bool revealRule; // 规律引导是否已揭晓

  DrillState copyWith({
    int? taskId,
    String? title,
    DrillSession? session,
    DrillPhase? phase,
    int? stepIndex,
    int? itemIndex,
    NpcMessage? npc,
    bool? busy,
    int? stars,
    bool? completed,
    bool? revealRule,
  }) =>
      DrillState(
        taskId: taskId ?? this.taskId,
        title: title ?? this.title,
        session: session ?? this.session,
        phase: phase ?? this.phase,
        stepIndex: stepIndex ?? this.stepIndex,
        itemIndex: itemIndex ?? this.itemIndex,
        npc: npc ?? this.npc,
        busy: busy ?? this.busy,
        stars: stars ?? this.stars,
        completed: completed ?? this.completed,
        revealRule: revealRule ?? this.revealRule,
      );
}

class DrillController extends Notifier<DrillState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  DrillState build() {
    ref.watch(currentChildIdProvider);
    return const DrillState();
  }

  void init({required int taskId, required String title, required String content}) {
    final session = parseDrillContent(content);
    state = DrillState(
      taskId: taskId,
      title: title,
      session: session,
      phase: DrillPhase.intro,
      npc: const NpcMessage('🔮', '准备好了吗？我们开始闯关吧！'),
    );
  }

  /// 进入四步。
  void startSteps() {
    state = state.copyWith(phase: DrillPhase.steps, stepIndex: 0, itemIndex: 0);
  }

  /// 揭示规律（观察→揭晓）。
  void revealRuleNow() {
    state = state.copyWith(revealRule: true);
  }

  /// 下一步：条目内推进或步间推进。
  void nextItem() {
    final s = state.session;
    if (s == null) return;
    final items = _currentItems(s);
    if (state.itemIndex + 1 < items.length) {
      state = state.copyWith(itemIndex: state.itemIndex + 1);
    } else if (state.stepIndex + 1 < s.steps.length) {
      state = state.copyWith(stepIndex: state.stepIndex + 1, itemIndex: 0);
    } else {
      state = state.copyWith(phase: DrillPhase.review);
    }
  }

  List<DrillItem> _currentItems(DrillSession s) {
    // 各步使用的条目池：认/记/用走 items；快测走 quiz（fallback items）
    return s.items.isNotEmpty ? s.items : s.reviewItems;
  }

  /// 提交「记/测」作答。
  Future<void> submitStep({required int itemId, required String answer, required bool requestHint}) async {
    final uid = _uid;
    final taskId = state.taskId;
    if (uid == null || taskId == null || state.busy) return;
    state = state.copyWith(busy: true);
    try {
      final r = await ref.read(drillRepositoryProvider).step(
            taskId: taskId,
            step: _currentStepName,
            itemId: itemId,
            answer: answer,
            requestHint: requestHint,
          );
      final correct = r['correct'] == true;
      final hint = '${r['hint'] ?? ''}';
      if (correct) {
        state = state.copyWith(
          busy: false,
          npc: NpcMessage('✨', '太棒了，答对啦！'),
        );
      } else if (r['reveal_answer'] == true) {
        state = state.copyWith(
          busy: false,
          npc: NpcMessage('💡', '没关系，答案是「${r['expected'] ?? ''}」，记牢它！'),
        );
      } else {
        state = state.copyWith(
          busy: false,
          npc: NpcMessage('💡', '哎呀，掉进陷阱啦！再想想${hint.isNotEmpty ? '：$hint' : ''}'),
        );
      }
    } catch (_) {
      state = state.copyWith(busy: false, npc: const NpcMessage('💡', '网络开小差了，再试一次吧'));
    }
  }

  /// 提交造句。
  Future<void> submitSentence({required int itemId, required String sentence}) async {
    final uid = _uid;
    final taskId = state.taskId;
    if (uid == null || taskId == null || state.busy) return;
    state = state.copyWith(busy: true);
    try {
      final r = await ref.read(drillRepositoryProvider).sentence(
            taskId: taskId,
            itemId: itemId,
            sentence: sentence,
          );
      final pass = r['pass'] == true;
      state = state.copyWith(
        busy: false,
        npc: pass
            ? const NpcMessage('✨', '搭配正确，用得好！')
            : NpcMessage('💡', '${r['feedback'] ?? '再试试把短语用进完整句子里'}'),
      );
    } catch (_) {
      state = state.copyWith(busy: false, npc: const NpcMessage('💡', '网络开小差了，再试一次吧'));
    }
  }

  /// 完成：批量提交结果，拿到星级。
  Future<void> complete({required Map<String, bool> results}) async {
    final uid = _uid;
    final taskId = state.taskId;
    if (uid == null || taskId == null || state.busy) return;
    state = state.copyWith(busy: true);
    try {
      final r = await ref.read(drillRepositoryProvider).complete(
            taskId: taskId,
            results: results,
          );
      state = state.copyWith(
        busy: false,
        stars: (r['stars'] as num?)?.toInt() ?? 1,
        completed: true,
        npc: const NpcMessage('🎉', '闯关完成！看看你的星星吧'),
      );
      try {
        await ref.read(homeRepositoryProvider).submitTask(taskId);
      } catch (_) {}
      try {
        ref.read(homeControllerProvider.notifier).reload();
      } catch (_) {}
    } catch (_) {
      state = state.copyWith(busy: false, npc: const NpcMessage('💡', '提交失败，再试一次吧'));
    }
  }

  String get _currentStepName {
    final s = state.session;
    if (s == null || s.steps.isEmpty) return 'recall';
    final i = state.stepIndex.clamp(0, s.steps.length - 1);
    return s.steps[i];
  }
}

final drillControllerProvider =
    NotifierProvider<DrillController, DrillState>(DrillController.new);
