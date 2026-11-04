import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/text_utils.dart';
import 'data/ask_repository.dart';

/// 对话的三种模式（对齐后端 capability：chat/visualize/solve）
enum AskMode {
  chat('对话'),
  visualize('可视化'),
  solve('解题');

  const AskMode(this.label);

  final String label;

  String get id => name;
}

class AskState {
  const AskState({
    this.messages = const [],
    this.mode = AskMode.chat,
    this.busy = false,
    this.toolHint,
    this.answer = '',
    this.lessonId,
    this.context = '',
    this.selected = '',
  });

  final List<AskMessage> messages;
  final AskMode mode;
  final bool busy;

  /// 当前 tool_call 的占位提示（如「正在查词…」）；非空时显示
  final String? toolHint;

  /// 流式累积中的答案（final 未到达前实时显示）
  final String answer;

  final int? lessonId;

  /// 课文全文（未选中引用时作为提问上下文）
  final String context;

  /// 当前选中的引用句子（非空时作为提问上下文，优先于全文）
  final String selected;

  /// 是否已初始化（未初始化时 send 直接返回）
  bool get ready => lessonId != null;

  AskState copyWith({
    List<AskMessage>? messages,
    AskMode? mode,
    bool? busy,
    String? Function()? toolHint,
    String? answer,
    int? lessonId,
    String? context,
    String? selected,
  }) =>
      AskState(
        messages: messages ?? this.messages,
        mode: mode ?? this.mode,
        busy: busy ?? this.busy,
        toolHint: toolHint != null ? toolHint() : this.toolHint,
        answer: answer ?? this.answer,
        lessonId: lessonId ?? this.lessonId,
        context: context ?? this.context,
        selected: selected ?? this.selected,
      );
}

class AskController extends Notifier<AskState> {
  @override
  AskState build() => const AskState();

  /// 从阅读页初始化（lessonId + 课文全文）
  void init({required int lessonId, required String context}) {
    state = AskState(lessonId: lessonId, context: context);
  }

  void setMode(AskMode mode) => state = state.copyWith(mode: mode);

  /// 设置/清除选中的引用句子
  void setSelected(String sentence) => state = state.copyWith(selected: sentence);

  Future<void> send(String question) async {
    final q = question.trim();
    if (q.isEmpty || state.busy) return;
    final lessonId = state.lessonId;
    if (lessonId == null) return;

    state = state.copyWith(
      messages: [...state.messages, AskMessage(role: 'user', text: q)],
      busy: true,
      toolHint: () => null,
      answer: '',
    );

    final repo = ref.read(askRepositoryProvider);
    final mode = state.mode;
    // 引用优先，否则用课文全文
    final ctx = state.selected.isNotEmpty ? state.selected : state.context;
    final sentences = splitSentences(ctx);

    String answer = '';
    List<int> citations = const [];
    String? toolHint;

    try {
      await for (final event in repo.askStream(
        lessonId: lessonId,
        question: q,
        context: ctx,
        mode: mode.id,
        sentences: sentences,
      )) {
        if (!ref.mounted) return;
        switch (event.type) {
          case 'tool_call':
            toolHint = _toolHint(event.data);
            state = state.copyWith(toolHint: () => toolHint);
          case 'tool_result':
            break;
          case 'final':
            answer = '${event.data['answer'] ?? ''}';
            final c = event.data['citations'];
            if (c is List) citations = c.whereType<num>().map((n) => n.toInt()).toList();
            state = state.copyWith(answer: answer, toolHint: () => null);
          case 'error':
            answer = '抱歉，回答出错：${event.data['error'] ?? '未知错误'}';
            state = state.copyWith(answer: answer, toolHint: () => null);
        }
      }
    } catch (_) {
      if (!ref.mounted) return;
      answer = '抱歉，网络异常，请稍后重试';
    }

    if (!ref.mounted) return;
    state = state.copyWith(
      messages: [...state.messages, AskMessage(role: 'ai', text: answer, citations: citations, mode: mode.id)],
      busy: false,
      answer: '',
      toolHint: () => null,
    );
  }

  String _toolHint(Map<String, dynamic> data) {
    final name = '${data['tool'] ?? data['name'] ?? '工具'}';
    return switch (name) {
      'lookup_word' => '正在查生词释义…',
      'search_text' => '正在检索课文…',
      'render_mermaid' => '正在生成图表…',
      _ => '正在思考…',
    };
  }
}

final askControllerProvider = NotifierProvider<AskController, AskState>(AskController.new);
