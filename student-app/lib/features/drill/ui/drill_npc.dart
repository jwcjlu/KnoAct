import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import '../drill_controller.dart';

/// NPC 精灵气泡：圆形 emoji 头像 + 带尾巴的气泡文案。
class NpcBubble extends StatelessWidget {
  const NpcBubble({super.key, required this.message, this.onTap});

  final NpcMessage message;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.blueSoft,
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.line),
            ),
            child: Text(message.emoji, style: const TextStyle(fontSize: 24)),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
              ),
              child: Text(
                message.text,
                style: const TextStyle(fontSize: 14, height: 1.5, color: AppColors.ink),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
