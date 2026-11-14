import 'package:flutter/material.dart';

/// 配色沿用旧版学生端（frontend/index.html 的 CSS 变量）
class AppColors {
  static const blue = Color(0xFF3158E8);
  static const blueSoft = Color(0xFFEDF1FF);
  static const green = Color(0xFF2E8B5A);
  static const greenSoft = Color(0xFFE8F7EF);
  static const orange = Color(0xFFDC872D);
  static const orangeSoft = Color(0xFFFFF2DF);
  static const gold = Color(0xFFF59D20);
  static const bg = Color(0xFFF7F8F5);
  static const ink = Color(0xFF202723);
  static const gray = Color(0xFF78817B);
  static const line = Color(0xFFE3E7E0);
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: AppColors.blue, primary: AppColors.blue, surface: Colors.white);
  return ThemeData(
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.bg,
    useMaterial3: true,
    // 中文字体回退：web 端默认 Roboto 不含中文字形，导致中文显示成方块；
    // 用系统字体回退保证中文正常显示（macOS 苹方 / Windows 微软雅黑 / 通用 Noto）
    fontFamilyFallback: const ['Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
    cardTheme: const CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(20)),
        side: BorderSide(color: AppColors.line),
      ),
    ),
  );
}
