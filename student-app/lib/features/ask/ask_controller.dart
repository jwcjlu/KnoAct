import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/text_utils.dart';
import '../reader/reader_controller.dart';
import 'data/ask_repository.dart';
import 'data/read_ask_cards_repository.dart';

class AskState {
  const AskState({
    this.messages = const [],
    this.modeId = 'chat',
    this.chatModel,
    this.busy = false,
    this.toolHint,
    this.answer = '',
    this.lessonId,
    this.context = '',
    this.selected = '',
  });

  final List<AskMessage> messages;

  /// Web `chatMode`：chat / visualize / solve 等
  final String modeId;

  /// Web `chatModel`：空表示用服务端默认
  final String? chatModel;
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
    String? modeId,
    String? Function()? chatModel,
    bool? busy,
    String? Function()? toolHint,
    String? answer,
    int? lessonId,
    String? context,
    String? selected,
  }) =>
      AskState(
        messages: messages ?? this.messages,
        modeId: modeId ?? this.modeId,
        chatModel: chatModel != null ? chatModel() : this.chatModel,
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
  AskState build() {
    ref.listen<int?>(
      readerControllerProvider.select((s) => s.currentLesson?.id),
      (prev, next) {
        if (next == null) return;
        if (prev == next && state.lessonId == next) return;
        _bindReaderLesson(prev != next);
      },
    );
    return _stateFromReader();
  }

  AskState _stateFromReader() {
    final lesson = ref.read(readerControllerProvider).currentLesson;
    if (lesson == null) return const AskState();
    final sentences = splitSentences(lesson.fullText);
    final quote = sentences.isNotEmpty ? sentences.first : '';
    return AskState(lessonId: lesson.id, context: lesson.fullText, selected: quote);
  }

  /// 首屏或 provider 重建后补绑课文（避免 send 时 lessonId 为空、Network 无请求）
  void ensureReaderBound() {
    if (state.lessonId != null) return;
    final fresh = _stateFromReader();
    if (fresh.lessonId == null) return;
    state = state.copyWith(lessonId: fresh.lessonId, context: fresh.context, selected: fresh.selected);
  }

  /// 个性化学习：课文随 [readerControllerProvider] 切换（在 Notifier 内 listen，避免 Widget build 期改 provider）
  void _bindReaderLesson(bool lessonChanged) {
    final lesson = ref.read(readerControllerProvider).currentLesson;
    if (lesson == null) return;
    final sentences = splitSentences(lesson.fullText);
    final quote = sentences.isNotEmpty ? sentences.first : '';
    state = AskState(
      lessonId: lesson.id,
      context: lesson.fullText,
      selected: lessonChanged ? quote : (state.selected.isNotEmpty ? state.selected : quote),
      modeId: state.modeId,
      chatModel: state.chatModel,
      messages: lessonChanged ? const [] : state.messages,
    );
  }

  /// 学习中心阅读材料等场景（无 reader 课文时手动绑定）
  void init({required int lessonId, required String context}) {
    state = AskState(lessonId: lessonId, context: context);
  }

  void setModeId(String modeId) => state = state.copyWith(modeId: modeId);

  void setChatModel(String? model) => state = state.copyWith(chatModel: () => model);

  /// 设置/清除选中的引用句子
  void setSelected(String sentence) => state = state.copyWith(selected: sentence);

  void pushAiMessage(String text, {String mode = 'chat', List<int> citations = const []}) {
    state = state.copyWith(
      messages: [...state.messages, AskMessage(role: 'ai', text: text, citations: citations, mode: mode)],
    );
  }

  /// Web `submitAskReplies` → `/api/ask/reply`
  Future<void> submitDiagnosticReplies({
    required int lessonId,
    required String context,
    required Map<String, String> replies,
  }) async {
    if (state.busy) return;
    state = state.copyWith(
      messages: [...state.messages, const AskMessage(role: 'user', text: '（回答了诊断性问题）')],
      busy: true,
      toolHint: () => null,
      answer: '',
    );
    String answer = '抱歉，回答出错了。';
    List<int> citations = const [];
    try {
      final r = await ref.read(readAskCardsRepositoryProvider).askReply(
            lessonId: lessonId,
            context: context,
            replies: replies,
          );
      answer = r.answer.isNotEmpty ? r.answer : '（暂无回答）';
      citations = r.citations;
    } catch (_) {}
    if (!ref.mounted) return;
    state = state.copyWith(
      messages: [...state.messages, AskMessage(role: 'ai', text: answer, citations: citations, mode: 'chat')],
      busy: false,
    );
  }

  Future<void> send(String question) async {
    final q = question.trim();
    if (q.isEmpty || state.busy) return;
    ensureReaderBound();
    final lessonId = state.lessonId;
    if (lessonId == null) return;

    state = state.copyWith(
      messages: [...state.messages, AskMessage(role: 'user', text: q)],
      busy: true,
      toolHint: () => null,
      answer: '',
    );

    final repo = ref.read(askRepositoryProvider);
    final mode = state.modeId;
    // 引用优先，否则用课文全文
    final ctx = state.selected.isNotEmpty ? state.selected : state.context;
    final sentences = splitSentences(ctx);

    String answer = '';
    List<int> citations = const [];
    String? toolHint;
    var gotFinal = false;

    Future<void> applySyncFallback() async {
      final sync = await repo.askOnce(
        lessonId: lessonId,
        question: q,
        context: ctx,
        mode: mode,
        model: state.chatModel,
        sentences: sentences,
      );
      answer = sync.answer.isNotEmpty ? sync.answer : '（暂无回答）';
      citations = sync.citations;
      gotFinal = true;
      if (ref.mounted) state = state.copyWith(answer: answer, toolHint: () => null);
    }

    try {
      await for (final event in repo.askStream(
        lessonId: lessonId,
        question: q,
        context: ctx,
        mode: mode,
        model: state.chatModel,
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
            gotFinal = true;
            answer = '${event.data['answer'] ?? ''}';
            final c = event.data['citations'];
            if (c is List) citations = c.whereType<num>().map((n) => n.toInt()).toList();
            state = state.copyWith(answer: answer, toolHint: () => null);
          case 'error':
            gotFinal = true;
            answer = '抱歉，回答出错：${event.data['error'] ?? '未知错误'}';
            state = state.copyWith(answer: answer, toolHint: () => null);
        }
      }
      if (!gotFinal) await applySyncFallback();
    } catch (_) {
      if (!ref.mounted) return;
      try {
        await applySyncFallback();
      } catch (_) {
        answer = '抱歉，网络异常，请稍后重试';
      }
    }

    if (!ref.mounted) return;
    state = state.copyWith(
      messages: [...state.messages, AskMessage(role: 'ai', text: answer, citations: citations, mode: mode)],
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
