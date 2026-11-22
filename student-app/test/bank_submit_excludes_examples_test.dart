import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/data/bank_repository.dart';
import 'package:student_app/features/bank_exercise/ui/bank_exercise_page.dart';

/// 记录提交负载，用来断言示例行不会被提交。
class _CapturingRepo implements BankRepository {
  final submitted = <List<Map<String, dynamic>>>[];

  @override
  Future<List<PracticeBank>> listPracticeBanks() async => const [];

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId,
      {List<int>? questionIds}) async {
    return const [
      BankQuestion(
        id: 1, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: '示例', options: [],
        groupId: 7, groupStem: '不计算，运用规律直接写出得数',
        seqInGroup: 1, isExample: true, workMode: 'pattern',
        answerKind: 'numeric_list', blankCount: 1, answer: '1.2',
      ),
      BankQuestion(
        id: 2, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: '待做', options: [],
        groupId: 7, groupStem: '不计算，运用规律直接写出得数',
        seqInGroup: 2, isExample: false, workMode: 'pattern',
        answerKind: 'numeric_list', blankCount: 1, answer: '12.3',
      ),
    ];
  }

  @override
  Future<BankSubmitResult> submit(
      {required int bankId, required List<Map<String, dynamic>> answers}) async {
    submitted.add(answers);
    return BankSubmitResult(score: 1, total: answers.length, answers: const []);
  }
}

void main() {
  testWidgets('提交时排除示例行', (tester) async {
    final repo = _CapturingRepo();
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

    await tester.enterText(find.byKey(const ValueKey('bank-blank-2')), '12.3');
    await tester.pump();

    await tester.tap(find.textContaining('提交答案'));
    await tester.pumpAndSettle();

    expect(repo.submitted, hasLength(1));
    final ids = repo.submitted.first.map((a) => a['question_id']).toList();
    expect(ids, [2], reason: '示例行（id=1）不应被提交，实际 $ids');
  });
}
