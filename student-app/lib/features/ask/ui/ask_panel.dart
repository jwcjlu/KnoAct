import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../ask_controller.dart';
import '../data/ask_repository.dart';
import '../mermaid_util.dart';
import '../mermaid_view.dart';

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
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  void _send(String text) {
    final q = text.trim();
    if (q.isEmpty) return;
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
    final hasMessages = s.messages.isNotEmpty || s.busy;
    if (disabled) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(disabledHint, style: const TextStyle(fontSize: 13, color: AppColors.gray, height: 1.45)),
      );
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      // 引用上下文
      if (s.selected.isNotEmpty) ...[
        _SelectedBar(text: s.selected, onClear: () => ctl.setSelected('')),
        const SizedBox(height: 8),
      ],
      // 模式切换
      SegmentedButton<AskMode>(
        segments: [
          for (final m in AskMode.values)
            ButtonSegment(
              value: m,
              label: Text(m.label),
              icon: Icon(m == AskMode.chat
                  ? Icons.chat_bubble_outline
                  : m == AskMode.visualize
                      ? Icons.donut_large
                      : Icons.lightbulb_outline),
            ),
        ],
        selected: {s.mode},
        onSelectionChanged: (v) => ctl.setMode(v.first),
      ),
      // 空态：只给输入框，紧凑不挤压答题区；有消息后才展开消息列表
      if (hasMessages) ...[
        const SizedBox(height: 8),
        ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 320),
          child: ListView(
            shrinkWrap: true,
            children: [
              for (final m in s.messages) _MessageBubble(message: m),
              if (s.busy) _StreamingBubble(answer: s.answer, toolHint: s.toolHint),
            ],
          ),
        ),
      ],
      const SizedBox(height: 8),
      // 快捷问题（空态时给出引导）
      Wrap(spacing: 8, children: [
        for (final q in const ['这段话是什么意思？', '帮我总结知识点', '给我出一道练习题'])
          ActionChip(
            label: Text(q, style: const TextStyle(fontSize: 12)),
            onPressed: s.busy ? null : () => _send(q),
          ),
      ]),
      const SizedBox(height: 8),
      // 输入框 + 发送
      Row(children: [
        Expanded(
          child: TextField(
            controller: _input,
            decoration: const InputDecoration(hintText: '针对课文提问…', isDense: true, border: OutlineInputBorder()),
            textInputAction: TextInputAction.send,
            onSubmitted: (_) => s.busy ? null : _send(_input.text),
          ),
        ),
        const SizedBox(width: 8),
        FilledButton(
          onPressed: s.busy ? null : () => _send(_input.text),
          child: const Icon(Icons.send),
        ),
      ]),
    ]);
  }
}

class _SelectedBar extends StatelessWidget {
  const _SelectedBar({required this.text, required this.onClear});

  final String text;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(color: AppColors.blueSoft, borderRadius: BorderRadius.circular(8)),
        child: Row(children: [
          Expanded(
            child: Text('引用：$text', style: const TextStyle(fontSize: 13, color: AppColors.blue), maxLines: 2, overflow: TextOverflow.ellipsis),
          ),
          GestureDetector(onTap: onClear, child: const Icon(Icons.close, size: 16, color: AppColors.blue)),
        ]),
      );
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final AskMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final mermaid = !isUser && message.mode == 'visualize' ? extractMermaid(message.text) : null;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isUser ? AppColors.blueSoft : Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: isUser ? null : Border.all(color: AppColors.line),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          if (mermaid != null)
            MermaidView(code: mermaid, height: 240)
          else
            Text(message.text, style: const TextStyle(height: 1.5)),
          if (message.citations.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '出处：${message.citations.map((c) => '第$c句').join('、')}',
              style: const TextStyle(fontSize: 12, color: AppColors.gray),
            ),
          ],
        ]),
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
