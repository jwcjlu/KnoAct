import 'package:flutter/material.dart';

/// 答 + 指四态的文案与配色。
///
/// 设计约束：
/// - `expression_weak`（答案错、出处对）**不得使用错误色**，也不得说「错」。
///   这类孩子理解到位、只是表达没到，正确的响应是帮他表述，不是否定。
/// - `lucky` 同理：答案确实是对的，不能让孩子以为自己做错了。
const _green = Color(0xFF2E8B5A);
const _amber = Color(0xFFDC872D);
const _gray = Color(0xFF78817B);

String quizVerdictText(String verdict) {
  switch (verdict) {
    case 'confirmed':
      return '对了，你找的这句正是关键。';
    case 'lucky':
      return '答案对了，但你说的这句不是依据。再看看哪句能支持它？';
    case 'expression_weak':
      return '你找的位置是对的，只是话没说明白。你想说的是什么？';
    case 'not_understood':
      return '我们回去再看看这一句。';
    default:
      return '';
  }
}

Color quizVerdictColor(String verdict) {
  switch (verdict) {
    case 'confirmed':
      return _green;
    case 'lucky':
    case 'not_understood':
      return _amber;
    case 'expression_weak':
      // 中性灰：理解是对的，不需要红叉
      return _gray;
    default:
      return _gray;
  }
}
