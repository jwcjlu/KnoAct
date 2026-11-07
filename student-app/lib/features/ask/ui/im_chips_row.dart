import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import 'im_chat_modes.dart';

/// Web `.im-chips`：默认模型 + 模式下拉（`showMenu` 走 Overlay，Web 点击可靠）
class ImChipsRow extends StatefulWidget {
  const ImChipsRow({
    super.key,
    required this.modeId,
    required this.onMode,
    required this.modelOptions,
    required this.defaultModel,
    this.selectedModel,
    required this.onModel,
    this.enabled = true,
  });

  final String modeId;
  final ValueChanged<String> onMode;
  final List<String> modelOptions;
  final String defaultModel;
  final String? selectedModel;
  final ValueChanged<String?> onModel;
  final bool enabled;

  @override
  State<ImChipsRow> createState() => _ImChipsRowState();
}

class _ImChipsRowState extends State<ImChipsRow> {
  final _modelKey = GlobalKey();
  final _modeKey = GlobalKey();

  Future<void> _openModeMenu() async {
    if (!widget.enabled) return;
    final picked = await _showAnchorMenu<String>(
      context: context,
      anchorKey: _modeKey,
      menuHeight: 300,
      builder: (ctx) => [
        for (final m in imChatModes)
          PopupMenuItem<String>(
            value: m.id,
            padding: EdgeInsets.zero,
            child: _ModeMenuRow(def: m, selected: widget.modeId == m.id),
          ),
      ],
    );
    if (picked != null && picked != widget.modeId) widget.onMode(picked);
    if (picked != null && picked == widget.modeId) widget.onMode(picked); // 同项再选也确认
  }

  Future<void> _openModelMenu() async {
    if (!widget.enabled) return;
    if (widget.modelOptions.isEmpty) return;
    final effective = widget.selectedModel ?? widget.defaultModel;
    final picked = await _showAnchorMenu<String>(
      context: context,
      anchorKey: _modelKey,
      menuHeight: 220,
      builder: (ctx) => [
        for (final m in widget.modelOptions)
          PopupMenuItem<String>(
            value: m,
            padding: EdgeInsets.zero,
            child: _MenuRow(title: m, showCheck: effective == m),
          ),
      ],
    );
    if (picked != null) widget.onModel(picked == widget.defaultModel ? null : picked);
  }

  @override
  Widget build(BuildContext context) {
    final modeDef = imChatModeById(widget.modeId) ?? imChatModes.first;
    final modelLabel = widget.selectedModel == null || widget.selectedModel!.isEmpty
        ? '默认模型'
        : shortModelName(widget.selectedModel!);

    return Row(
      children: [
        KeyedSubtree(
          key: _modelKey,
          child: _ImComposerChip(
            label: modelLabel,
            icon: Icons.psychology_outlined,
            active: widget.selectedModel != null && widget.selectedModel!.isNotEmpty,
            onTap: widget.enabled ? _openModelMenu : null,
          ),
        ),
        const SizedBox(width: 6),
        KeyedSubtree(
          key: _modeKey,
          child: _ImComposerChip(
            label: modeDef.name,
            icon: modeDef.icon,
            active: true,
            onTap: widget.enabled ? _openModeMenu : null,
          ),
        ),
      ],
    );
  }
}

Future<T?> _showAnchorMenu<T>({
  required BuildContext context,
  required GlobalKey anchorKey,
  required double menuHeight,
  required List<PopupMenuEntry<T>> Function(BuildContext) builder,
}) async {
  final anchorCtx = anchorKey.currentContext;
  if (anchorCtx == null) return null;
  final box = anchorCtx.findRenderObject() as RenderBox?;
  if (box == null || !box.hasSize) return null;
  final overlay = Overlay.of(context).context.findRenderObject() as RenderBox;
  final topLeft = box.localToGlobal(Offset.zero, ancestor: overlay);
  final bottomRight = box.localToGlobal(box.size.bottomRight(Offset.zero), ancestor: overlay);

  // 菜单优先在 chip 上方展开（composer 在底部）
  final rect = Rect.fromLTRB(
    topLeft.dx,
    (topLeft.dy - menuHeight).clamp(0.0, overlay.size.height),
    bottomRight.dx,
    topLeft.dy,
  );

  return showMenu<T>(
    context: context,
    position: RelativeRect.fromRect(rect, Offset.zero & overlay.size),
    color: Colors.white,
    surfaceTintColor: Colors.white,
    elevation: 8,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: const BorderSide(color: Color(0xFFE3E6E2)),
    ),
    constraints: BoxConstraints(
      minWidth: 180,
      maxWidth: 260,
      maxHeight: menuHeight,
    ),
    items: builder(context),
  );
}

class _MenuRow extends StatelessWidget {
  const _MenuRow({required this.title, this.showCheck = false});

  final String title;
  final bool showCheck;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          children: [
            Expanded(child: Text(title, style: const TextStyle(fontSize: 13))),
            if (showCheck) const Icon(Icons.check, size: 16, color: AppColors.blue),
          ],
        ),
      );
}

class _ModeMenuRow extends StatelessWidget {
  const _ModeMenuRow({required this.def, required this.selected});

  final ImChatModeDef def;
  final bool selected;

  @override
  Widget build(BuildContext context) => Container(
        color: selected ? const Color(0xFFEEF2FF) : Colors.transparent,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(def.icon, size: 14, color: selected ? AppColors.blue : const Color(0xFF4B544E)),
            const SizedBox(width: 6),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    def.name,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                      color: selected ? AppColors.blue : const Color(0xFF2B332E),
                    ),
                  ),
                  Text(
                    def.desc,
                    style: TextStyle(fontSize: 11, color: selected ? const Color(0xFF7C86D8) : const Color(0xFF8E9691)),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
}

class _ImComposerChip extends StatelessWidget {
  const _ImComposerChip({required this.label, required this.icon, required this.active, this.onTap});

  final String label;
  final IconData icon;
  final bool active;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: active ? const Color(0xFFEEF2FF) : Colors.white,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: active ? AppColors.blue : const Color(0xFFE3E6E2)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 14, color: active ? AppColors.blue : const Color(0xFF4B544E)),
                const SizedBox(width: 4),
                Text(label, style: TextStyle(fontSize: 12, color: active ? AppColors.blue : const Color(0xFF4B544E))),
                const SizedBox(width: 2),
                Icon(Icons.arrow_drop_down, size: 16, color: active ? AppColors.blue : const Color(0xFF4B544E).withValues(alpha: 0.55)),
              ],
            ),
          ),
        ),
      );
}
