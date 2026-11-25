import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/expression/ui/expression_done_view.dart';

/// 结束页不能有任何评价性语言：本功能不做判定，评价就是撒谎。
void main() {
  testWidgets('结束页只说记下来了，不评价', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ExpressionDoneView())),
    );

    expect(find.textContaining('记下来了'), findsOneWidget);
    expect(
      find.textContaining(RegExp(r'看到|爸爸/妈妈')),
      findsOneWidget,
      reason: '应说明家长能看到讲解',
    );

    const banned = ['好', '棒', '正确', '完整', '不错', '优秀', '错', '厉害', '真棒'];
    for (final word in banned) {
      expect(
        find.textContaining(word),
        findsNothing,
        reason: '结束页不该出现「$word」——本功能不判定',
      );
    }
  });

  testWidgets('结束页有「再讲一个」和「返回」', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ExpressionDoneView())),
    );
    expect(find.text('再讲一个'), findsOneWidget);
    expect(find.text('返回'), findsOneWidget);
  });
}
