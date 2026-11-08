import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/data/bank_repository.dart';
import 'package:student_app/features/bank_exercise/ui/bank_exercise_page.dart';

class FakePassageBankRepository implements BankRepository {
  @override
  Future<List<PracticeBank>> listPracticeBanks() async => const [];

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId, {List<int>? questionIds}) async {
    const p = ReadingPassageInfo(id: 3, title: '小蝌蚪找妈妈', content: '小蝌蚪 **游啊游**。');
    return const [
      BankQuestion(
        id: 2,
        qtype: 'short_answer',
        qtypeCategory: 'subjective',
        question: '谁在游？',
        options: [],
        passageId: 3,
        passage: p,
      ),
    ];
  }

  @override
  Future<BankSubmitResult> submit({required int bankId, required List<Map<String, dynamic>> answers}) async {
    return const BankSubmitResult(score: 1, total: 1, answers: []);
  }
}

class FakeBankRepository implements BankRepository {
  @override
  Future<List<PracticeBank>> listPracticeBanks() async => const [];

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId, {List<int>? questionIds}) async {
    return const [
      BankQuestion(
        id: 1,
        qtype: 'single_choice',
        qtypeCategory: 'choice',
        question: '1+1=?',
        options: [
          BankOption(label: '2', value: 0),
          BankOption(label: '1', value: 1),
        ],
      ),
    ];
  }

  @override
  Future<BankSubmitResult> submit({required int bankId, required List<Map<String, dynamic>> answers}) async {
    return const BankSubmitResult(score: 1, total: 1, answers: []);
  }
}

void main() {
  testWidgets('题库练习页渲染题干与选项', (tester) async {
    final router = GoRouter(
      routes: [GoRoute(path: '/', builder: (_, __) => const BankExercisePage(bankId: 9))],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [bankRepositoryProvider.overrideWithValue(FakeBankRepository())],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pump();
    await tester.pumpAndSettle();
    expect(find.textContaining('1+1=?'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    expect(find.text('1'), findsOneWidget);
  });

  testWidgets('阅读理解先展示材料再展示子题', (tester) async {
    final router = GoRouter(
      routes: [GoRoute(path: '/', builder: (_, __) => const BankExercisePage(bankId: 9))],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [bankRepositoryProvider.overrideWithValue(FakePassageBankRepository())],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pump();
    await tester.pumpAndSettle();
    expect(find.text('小蝌蚪找妈妈'), findsOneWidget);
    expect(find.textContaining('游啊游'), findsWidgets);
    expect(find.textContaining('谁在游'), findsOneWidget);
  });
}
