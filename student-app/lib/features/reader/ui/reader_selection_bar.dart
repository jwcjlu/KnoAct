import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import '../models/reader_selection.dart';

const annotSwatch = <String, Color>{
  'yellow': Color(0xFFFACD5A),
  'green': Color(0xFF8CDB94),
  'blue': Color(0xFF7AC0FA),
  'pink': Color(0xFFFAA1C7),
  'purple': Color(0xFFC7AEFA),
};

/// 对齐 Web `#reader-popover`：色板 + 标注 + 追问。
class ReaderSelectionBar extends StatefulWidget {
  const ReaderSelectionBar({
    super.key,
    required this.selection,
    required this.chatDisabled,
    required this.annotColor,
    required this.onPickColor,
    required this.onHighlight,
    required this.onUnderline,
    required this.onSaveNote,
    required this.onGlossary,
    required this.onAsk,
    required this.onExplain,
    required this.onTranslate,
    required this.onClose,
  });

  final ReaderSelection selection;
  final bool chatDisabled;
  final String annotColor;
  final ValueChanged<String> onPickColor;
  final VoidCallback onHighlight;
  final VoidCallback onUnderline;
  final void Function(String note) onSaveNote;
  final VoidCallback onGlossary;
  final VoidCallback onAsk;
  final VoidCallback onExplain;
  final VoidCallback onTranslate;
  final VoidCallback onClose;

  @override
  State<ReaderSelectionBar> createState() => _ReaderSelectionBarState();
}

class _ReaderSelectionBarState extends State<ReaderSelectionBar> {
  bool _noteOpen = false;
  final _noteController = TextEditingController();

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.selection.quote;
    if (q.length < 2) return const SizedBox.shrink();

    return Material(
      elevation: 8,
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Wrap(
                    spacing: 6,
                    children: [
                      for (final e in annotSwatch.entries)
                        InkWell(
                          onTap: () => widget.onPickColor(e.key),
                          customBorder: const CircleBorder(),
                          child: Container(
                            width: 22,
                            height: 22,
                            decoration: BoxDecoration(
                              color: e.value,
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: widget.annotColor == e.key ? AppColors.blue : AppColors.line,
                                width: widget.annotColor == e.key ? 2 : 1,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  onPressed: widget.onClose,
                  icon: const Icon(Icons.close, size: 18),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Wrap(
              spacing: 4,
              runSpacing: 4,
              children: [
                _ActionChip(icon: Icons.border_color, label: '划线', onTap: widget.onHighlight),
                _ActionChip(icon: Icons.format_underline, label: '下划线', onTap: widget.onUnderline),
                _ActionChip(icon: Icons.edit_note, label: '笔记', onTap: () => setState(() => _noteOpen = !_noteOpen)),
                _ActionChip(icon: Icons.menu_book_outlined, label: '生词', onTap: widget.onGlossary),
              ],
            ),
            if (!widget.chatDisabled) ...[
              const SizedBox(height: 6),
              Wrap(
                spacing: 6,
                children: [
                  FilledButton.icon(
                    onPressed: widget.onAsk,
                    icon: const Icon(Icons.chat_bubble_outline, size: 16),
                    label: const Text('追问'),
                  ),
                  OutlinedButton(onPressed: widget.onExplain, child: const Text('解释')),
                  OutlinedButton(onPressed: widget.onTranslate, child: const Text('翻译')),
                ],
              ),
            ],
            if (_noteOpen) ...[
              const SizedBox(height: 8),
              Text('「$q」', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
              const SizedBox(height: 6),
              TextField(
                controller: _noteController,
                maxLines: 3,
                decoration: const InputDecoration(
                  hintText: '给这段文字写一句笔记…',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(onPressed: () => setState(() => _noteOpen = false), child: const Text('取消')),
                  FilledButton(
                    onPressed: () {
                      widget.onSaveNote(_noteController.text.trim());
                      setState(() => _noteOpen = false);
                    },
                    child: const Text('保存笔记'),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ActionChip extends StatelessWidget {
  const _ActionChip({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 18),
      label: Text(label),
      style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
    );
  }
}
