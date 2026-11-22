import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/data/bank_repository.dart';
import 'package:student_app/features/bank_exercise/ui/bank_exercise_page.dart';

/// 记录 fetchQuestions 收到的参数，并用真实任务数据返回题目。
class _RecordingRepo implements BankRepository {
  int? lastBankId;
  List<int>? lastIds;
  List<int>? lastExtra;

  @override
  Future<List<PracticeBank>> listPracticeBanks() async => const [];

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId,
      {List<int>? questionIds, List<int>? extraBankIds}) async {
    lastBankId = bankId;
    lastIds = questionIds;
    lastExtra = extraBankIds;
    // 模拟真实数据：两套卷各 3 道
    return const [
      BankQuestion(
        id: 5694, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: r'$0.26 + 0.45 =$ ____', options: [],
        groupId: 14, groupStem: '直接写出得数。（建议 2 分钟完成）',
        seqInGroup: 1, isExample: false, workMode: 'oral',
        answerKind: 'number', blankCount: 1, answer: '0.71',
      ),
      BankQuestion(
        id: 5636, qtype: 'fill_blank', qtypeCategory: 'blank',
        question: r'$0.48 \div 4.8 =$ ____', options: [],
        groupId: 7, groupStem: '直接写出得数。（建议2分钟完成）',
        seqInGroup: 1, isExample: false, workMode: 'oral',
        answerKind: 'number', blankCount: 1, answer: '0.1',
      ),
    ];
  }

  @override
  Future<BankSubmitResult> submit(
          {required int bankId, required List<Map<String, dynamic>> answers}) async =>
      BankSubmitResult(score: answers.length, total: answers.length, answers: const []);
}

void main() {
  testWidgets('BankExercisePage 收到多卷参数并渲染题目', (tester) async {
    final repo = _RecordingRepo();
    // 页面里的 TaskPageNavRow 需要 GoRouter 上下文
    final router = GoRouter(
      initialLocation: '/ex',
      routes: [
        GoRoute(
          path: '/home',
          builder: (_, _) => const Scaffold(body: Text('HOME')),
        ),
        GoRoute(
          path: '/ex',
          builder: (_, _) => const BankExercisePage(
            bankId: 8,
            questionIds: [5694, 5636],
            extraBankIds: [9],
            taskId: 519,
          ),
        ),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [bankRepositoryProvider.overrideWithValue(repo)],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // 仓库应收到多卷参数
    expect(repo.lastBankId, 8);
    expect(repo.lastIds, [5694, 5636]);
    expect(repo.lastExtra, [9], reason: 'extraBankIds 应透传到 repository');

    // 题组题干应出现（两套卷各自的 stem）
    expect(find.textContaining('建议 2 分钟完成'), findsWidgets);
    expect(find.textContaining('建议2分钟完成'), findsWidgets);
  });
}
