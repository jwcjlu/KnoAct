import 'package:flutter/material.dart';

/// 三个思维训练游戏统一配色。
///
/// 参考经典数独 / 舒尔特方格 / Windows 扫雷的观感；所有颜色集中于此，
/// 想整体换色只改这个文件。
class BrainPalette {
  const BrainPalette._();

  // ── 数独（白底 + 深蓝格线，粗线分宫）────────────────────────────
  static const sudokuBg = Colors.white;

  /// 每格细线：一屏缩小后仍要看得清，用中等深度的灰蓝
  static const sudokuLine = Color(0xFF55618A);
  static const sudokuBoxLine = Color(0xFF16234F);
  static const sudokuGiven = Color(0xFF1D2433);
  static const sudokuInput = Color(0xFF3158E8);
  static const sudokuSelected = Color(0x3D3158E8);
  static const sudokuPeer = Color(0x143158E8);
  static const sudokuWrong = Color(0x4DC05B4A);
  static const sudokuPadBg = Color(0xFFEDF1FF);

  // ── 舒尔特方格（暖白底 + 陶土橙强调色）──────────────────────────
  static const schulteBg = Color(0xFFFBF7F2);
  static const schulteTile = Colors.white;
  static const schulteTileBorder = Color(0xFFEADFD3);
  static const schulteTileText = Color(0xFF3E2F28);
  static const schulteAccent = Color(0xFFC2653B);
  static const schulteCleared = Color(0xFFE6EFE6);

  // ── 数字扫雷（经典灰 + 黑色 LCD + 红色数字）─────────────────────
  static const mineBg = Color(0xFFBFBFBF);
  static const minePanelBg = Color(0xFFBFBFBF);
  static const mineLcd = Color(0xFF1A1A1A);
  static const mineDigits = Color(0xFFFF3B30);
  static const mineClosed = Color(0xFFC0C0C0);
  static const mineOpen = Color(0xFFD6D6D6);

  /// 已开格之间的分隔线：要比格子底色明显更深，否则一片灰看不出格
  static const mineOpenLine = Color(0xFF8A8A8A);
  static const mineBevelLight = Colors.white;
  static const mineBevelDark = Color(0xFF7B7B7B);
  static const mineGridLine = Color(0xFF9A9A9A);

  /// 踩中的那颗雷的红底
  static const mineHit = Color(0xFFD93A2B);

  /// 扫雷数字 1–8 的经典配色。
  static const mineNumber = <int, Color>{
    1: Color(0xFF0000FF),
    2: Color(0xFF008000),
    3: Color(0xFFFE0000),
    4: Color(0xFF000080),
    5: Color(0xFF800000),
    6: Color(0xFF008080),
    7: Color(0xFF000000),
    8: Color(0xFF808080),
  };
}
