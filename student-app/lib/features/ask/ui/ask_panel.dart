import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../ask_controller.dart';
import '../data/ask_ai_config.dart';
import '../data/ask_repository.dart';
import '../mermaid_util.dart';
import '../mermaid_view.dart';
import '../immersive_quiz_controller.dart';
import 'im_chat_modes.dart';
import 'im_chips_row.dart';
import 'im_composer_styles.dart';
import 'immersive_quiz_cards.dart';

/// 内嵌在阅读页里的对话栏：模式切换 + 快捷问题 + 消息列表 + 输入框
class AskPanel extends ConsumerStatefulWidget {
  const AskPanel({super.key, this.chatDisabled = false, this.chatDisabledHint});

  /// 做作业等场景暂停对话（对齐 Web `chatDisabled`）
  final bool chatDisabled;
  final String? chatDisabledHint;

  @override
  ConsumerState<AskPanel> createState() => _AskPanelState();
}

class _AskPanelState extends ConsumerState<AskPanel> {
  final _input = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ref.read(askControllerProvider.notifier).ensureReaderBound();
    });
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  void _send(String text) {
    final q = text.trim();
    if (q.isEmpty) return;
    final modeId = ref.read(askControllerProvider).modeId;
    if (modeId == 'quiz') {
      ref.read(immersiveQuizProvider.notifier).start();
      return;
    }
    if (modeId == 'questions') {
      ref.read(immersiveDiagnosticProvider.notifier).start();
      return;
    }
    if (!imModeUsesAskStream(modeId)) {
      if (modeId == 'more') {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('更多能力即将上线')));
      }
      return;
    }
    final ctl = ref.read(askControllerProvider.notifier);
    if (!ref.read(askControllerProvider).ready) {
      ctl.ensureReaderBound();
      if (!ref.read(askControllerProvider).ready) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('课文还在加载，请稍后再问')));
        return;
      }
    }
    _input.clear();
    ref.read(askControllerProvider.notifier).send(q);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(askControllerProvider);
    final ctl = ref.read(askControllerProvider.notifier);
    final disabled = widget.chatDisabled;
    final disabledHint = widget.chatDisabledHint ??
        '本课作业还没完成，AI 对话已暂停；完成作业或点「先不做了」后即可继续提问';
    final quiz = ref.watch(immersiveQuizProvider);
    final diag = ref.watch(immersiveDiagnosticProvider);
    final hasMessages = s.messages.isNotEmpty || s.busy || quiz.active || quiz.busy || diag.active || diag.busy;
    if (disabled) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Expanded(child: SizedBox.shrink()),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 18),
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: Color(0xFFF0F2EF))),
              color: Colors.white,
            ),
            child: Text(disabledHint, style: const TextStyle(fontSize: 12.5, color: Color(0xFF8E9691), height: 1.7)),
          ),
        ],
      );
    }
    return LayoutBuilder(builder: (context, constraints) {
      final compactComposer = constraints.maxHeight < 320;
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (s.selected.isNotEmpty) ...[
        _ImCtxBar(text: s.selected, onClear: () => ctl.setSelected('')),
      ],
      Expanded(
        child: hasMessages
            ? ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                children: [
                  for (final m in s.messages) _MessageBubble(message: m),
                  if (s.busy && !quiz.active && !diag.active) _StreamingBubble(answer: s.answer, toolHint: s.toolHint),
                  if (quiz.busy && !quiz.active)
                    const Align(
                      alignment: Alignment.centerLeft,
                      child: Padding(
                        padding: EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
                            SizedBox(width: 8),
                            Text('正在出题…', style: TextStyle(color: AppColors.gray)),
                          ],
                        ),
                      ),
                    ),
                  const ImmersiveQuizCard(),
                  const ImmersiveDiagnosticCard(),
                ],
              )
            : const _ImEmptyWelcome(),
      ),
      ConstrainedBox(
        constraints: BoxConstraints(maxHeight: compactComposer ? 168 : 220),
        child: SingleChildScrollView(
          primary: false,
          child: _ImComposer(
            compact: compactComposer,
            busy: s.busy || quiz.busy || diag.busy,
            onSend: _send,
            controller: _input,
          ),
        ),
      ),
    ]);
    });
  }
}

/// Web `im-composer`：模型/模式下拉 chip + 快捷问题 + 输入框
class _ImComposer extends ConsumerWidget {
  const _ImComposer({required this.busy, required this.onSend, required this.controller, this.compact = false});

  final bool busy;
  final bool compact;
  final void Function(String) onSend;
  final TextEditingController controller;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(askControllerProvider);
    final ctl = ref.read(askControllerProvider.notifier);
    final cfg = ref.watch(askAiConfigProvider).maybeWhen(data: (c) => c, orElse: () => const AskAiConfig());

    return Container(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: Color(0xFFF0F2EF))),
          color: Colors.white,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          ImChipsRow(
            modeId: s.modeId,
            onMode: ctl.setModeId,
            modelOptions: cfg.modelOptions,
            defaultModel: cfg.defaultModel,
            selectedModel: s.chatModel,
            onModel: ctl.setChatModel,
            enabled: !busy,
          ),
          if (!compact) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final q in const ['这段话是什么意思？', '帮我总结知识点', '给我出一道练习题'])
                  ImQuickChip(label: q, enabled: !busy, onTap: () => onSend(q)),
              ],
            ),
            const SizedBox(height: 8),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  minLines: 1,
                  maxLines: 4,
                  decoration: InputDecoration(
                    hintText: '针对这段教材提问…',
                    hintStyle: const TextStyle(fontSize: 13.5, color: Color(0xFF8E9691)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
                    filled: true,
                    fillColor: Colors.white,
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFE3E6E2)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: AppColors.blue),
                    ),
                  ),
                  style: const TextStyle(fontSize: 13.5, height: 1.5, color: Color(0xFF2B332E)),
                  textInputAction: TextInputAction.send,
                  onSubmitted: busy ? null : (_) => onSend(controller.text),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 40,
                height: 40,
                child: Material(
                  color: busy ? const Color(0xFFC4CBCE) : AppColors.blue,
                  borderRadius: BorderRadius.circular(12),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: busy ? null : () => onSend(controller.text),
                    child: const Icon(Icons.arrow_upward, color: Colors.white, size: 20),
                  ),
                ),
              ),
            ],
          ),
        ]),
      );
  }
}

/// Web `.im-empty`：空对话时占满 `im-chat-body`，避免中间大块留白
class _ImEmptyWelcome extends StatelessWidget {
  const _ImEmptyWelcome();

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.auto_stories_outlined, size: 56, color: const Color(0xFFC4CAC6)),
              const SizedBox(height: 16),
              const Text(
                '边读边问，随时解惑',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2B332E),
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '选中正文里任意一段，就能追问、解释或翻译它；AI 的回答会指明出自原文的哪一处。',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12.5, height: 1.7, color: Color(0xFF8E9691)),
              ),
            ],
          ),
        ),
      );
}

/// Web `im-ctx`
class _ImCtxBar extends StatelessWidget {
  const _ImCtxBar({required this.text, required this.onClear});

  final String text;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: const Color(0xFFF3F6FF),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFFE0E8FF)),
          ),
          child: Row(children: [
            Expanded(
              child: Text('引用：$text', style: const TextStyle(fontSize: 12, color: Color(0xFF5A635C)), maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
            GestureDetector(onTap: onClear, child: const Text('×', style: TextStyle(fontSize: 16, color: Color(0xFF8E9691)))),
          ]),
        ),
      );
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final AskMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final mermaid = !isUser && (message.mode == 'visualize' || extractMermaid(message.text) != null)
        ? extractMermaid(message.text)
        : null;
    final bodyText = mermaid != null ? stripMermaidFence(message.text) : message.text;
    final modeId = message.mode ?? 'chat';
    final modeName = imChatModeById(modeId)?.name;
    final showModeTag = !isUser && modeName != null && modeName != '对话';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          if (showModeTag)
            Container(
              margin: const EdgeInsets.only(bottom: 2),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(color: const Color(0xFFEEF2FF), borderRadius: BorderRadius.circular(6)),
              child: Text(modeName, style: const TextStyle(fontSize: 10, color: Color(0xFF7C86D8))),
            ),
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
            constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.94),
            decoration: BoxDecoration(
              color: isUser ? AppColors.blue : const Color(0xFFF3F5F2),
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(14),
                topRight: const Radius.circular(14),
                bottomLeft: Radius.circular(isUser ? 4 : 14),
                bottomRight: Radius.circular(isUser ? 14 : 4),
              ),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
              if (mermaid != null) ...[
                MermaidView(code: mermaid, height: 200),
                if (bodyText.trim().isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(bodyText, style: const TextStyle(height: 1.65, fontSize: 13.5, color: Color(0xFF2B332E))),
                ],
              ] else
                Text(message.text, style: TextStyle(height: 1.65, fontSize: 13.5, color: isUser ? Colors.white : const Color(0xFF2B332E))),
              if (message.citations.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  '出处：${message.citations.map((c) => '第$c句').join('、')}',
                  style: TextStyle(fontSize: 10.5, color: isUser ? Colors.white70 : const Color(0xFFAAB1AB)),
                ),
              ],
            ]),
          ),
        ],
      ),
    );
  }
}

class _StreamingBubble extends StatelessWidget {
  const _StreamingBubble({required this.answer, required this.toolHint});

  final String answer;
  final String? toolHint;

  @override
  Widget build(BuildContext context) {
    final hint = toolHint;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.line),
        ),
        child: hint != null && answer.isEmpty
            ? Row(mainAxisSize: MainAxisSize.min, children: [
                const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
                const SizedBox(width: 8),
                Text(hint, style: const TextStyle(color: AppColors.gray)),
              ])
            : Text(answer, style: const TextStyle(height: 1.5)),
      ),
    );
  }
}
