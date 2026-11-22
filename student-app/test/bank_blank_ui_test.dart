import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/data/bank_repository.dart';
import 'package:student_app/features/bank_exercise/ui/bank_exercise_page.dart';

/// 一个题组：3 个示例 + 2 个待做（一个多空、一个单空）+ 一个比较大小题。
class _GroupedRepo implements BankRepository {
  @override
  Future<List<PracticeBank>> listPracticeBanks() async => const [];

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId,
      {List<int>? questionIds, List<int>? extraBankIds}) async {
    return const [
      // 组 7：找规律，2 个示例 + 1 个多空待做
      BankQuestion(
        id: 1, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: r'$1.08 \div 0.9 = 1.2$', options: [],
        groupId: 7, groupStem: '不计算，运用规律直接写出得数',
        seqInGroup: 1, isExample: true, workMode: 'pattern',
        answerKind: 'numeric_list', blankCount: 1, answer: '1.2',
      ),
      BankQuestion(
        id: 2, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: r'$11.106 \div 0.9 = 12.34$', options: [],
        groupId: 7, groupStem: '不计算，运用规律直接写出得数',
        seqInGroup: 2, isExample: true, workMode: 'pattern',
        answerKind: 'numeric_list', blankCount: 1, answer: '12.34',
      ),
      BankQuestion(
        id: 3, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: r'$1111.05 \div 0.9 =$ ____', options: [],
        groupId: 7, groupStem: '不计算，运用规律直接写出得数',
        seqInGroup: 3, isExample: false, workMode: 'pattern',
        answerKind: 'numeric_list', blankCount: 2, answer: '1234.5, 12345',
      ),
      // 组 8：比较大小
      BankQuestion(
        id: 4, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: '30.5 ○ 3.05', options: [],
        groupId: 8, groupStem: '比较大小',
        seqInGroup: 1, isExample: false, workMode: 'compare',
        answerKind: 'symbol', blankCount: 1, answer: '>',
      ),
    ];
  }

  @override
  Future<BankSubmitResult> submit(
      {required int bankId, required List<Map<String, dynamic>> answers}) async {
    return const BankSubmitResult(score: 2, total: 2, answers: []);
  }
}

Future<void> _pump(WidgetTester tester, BankRepository repo) async {
  final router = GoRouter(
    routes: [GoRoute(path: '/', builder: (_, _) => const BankExercisePage(bankId: 9))],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [bankRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pump();
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('题组题干出现一次，示例块标注「不用做」', (tester) async {
    await _pump(tester, _GroupedRepo());
    expect(find.textContaining('不计算，运用规律直接写出得数'), findsOneWidget);
    expect(find.textContaining('已印好的示例'), findsOneWidget);
    expect(find.textContaining('比较大小'), findsOneWidget);
  });

  testWidgets('多空题按 blankCount 渲染 2 个输入框', (tester) async {
    await _pump(tester, _GroupedRepo());
    // 题组 7 的多空题（id=3）应有两个空 key
    expect(find.byKey(const ValueKey('bank-blank-3-0')), findsOneWidget);
    expect(find.byKey(const ValueKey('bank-blank-3-1')), findsOneWidget);
  });

  testWidgets('示例行不出现输入框', (tester) async {
    await _pump(tester, _GroupedRepo());
    // 示例题 id=1 / id=2 不该有输入框
    expect(find.byKey(const ValueKey('bank-blank-1')), findsNothing);
    expect(find.byKey(const ValueKey('bank-blank-1-0')), findsNothing);
    expect(find.byKey(const ValueKey('bank-blank-2')), findsNothing);
    expect(find.byKey(const ValueKey('bank-blank-2-0')), findsNothing);
  });

  testWidgets('比较大小题渲染 > < = 三个按钮', (tester) async {
    await _pump(tester, _GroupedRepo());
    expect(find.widgetWithText(ChoiceChip, '>'), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, '<'), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, '='), findsOneWidget);
  });

  testWidgets('填两个空后都进入 state', (tester) async {
    await _pump(tester, _GroupedRepo());
    await tester.enterText(find.byKey(const ValueKey('bank-blank-3-0')), '1234.5');
    await tester.enterText(find.byKey(const ValueKey('bank-blank-3-1')), '12345');
    await tester.pump();
    // 两个框各自保留了输入内容
    expect(find.text('1234.5'), findsOneWidget);
    expect(find.text('12345'), findsOneWidget);
  });
}
