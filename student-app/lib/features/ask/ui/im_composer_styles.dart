import 'package:flutter/material.dart';

import '../../../core/theme.dart';

/// Web `im-chip` / `qa-btn` 视觉（frontend/index.html）
class ImChip extends StatelessWidget {
  const ImChip({super.key, required this.label, required this.selected, required this.onTap, this.icon});

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: selected ? AppColors.blueSoft : Colors.white,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: selected ? AppColors.blue : const Color(0xFFE3E6E2)),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (icon != null) ...[
                Icon(icon, size: 14, color: selected ? AppColors.blue : const Color(0xFF4B544E)),
                const SizedBox(width: 4),
              ],
              Text(label, style: TextStyle(fontSize: 12, color: selected ? AppColors.blue : const Color(0xFF4B544E))),
            ]),
          ),
        ),
      );
}

class ImQuickChip extends StatelessWidget {
  const ImQuickChip({super.key, required this.label, required this.onTap, this.enabled = true});

  final String label;
  final VoidCallback? onTap;
  final bool enabled;

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: enabled ? onTap : null,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: const Color(0xFFE3E6E2)),
            ),
            child: Text(label, style: TextStyle(fontSize: 12, color: enabled ? const Color(0xFF4B544E) : AppColors.gray)),
          ),
        ),
      );
}
