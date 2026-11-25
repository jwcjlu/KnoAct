import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/expression/data/expression_repository.dart';
import 'package:student_app/features/expression/ui/expression_page.dart';

const _topic = ExpressionTopic(kind: 'knowledge_point', id: 7, title: '比喻');

class FakeExpressionRepository extends ExpressionRepository {
  FakeExpressionRepository() : super(ApiClient('http://test.invalid'));

  Object? topicsError;
  Object? createNoteError;
  List<ExpressionTopic> topicsResult = const [];

  @override
  Future<List<ExpressionTopic>> topics({required int userId}) async {
    final error = topicsError;
    if (error != null) throw error;
    return topicsResult;
  }

  @override
  Future<void> createNote({
    required int userId,
    int? knowledgePointId,
    int? itemId,
    required String text,
    List<Map<String, String>>? probeTurns,
  }) async {
    final error = createNoteError;
    if (error != null) throw error;
  }
}

Future<void> _pumpPage(
  WidgetTester tester,
  FakeExpressionRepository repository,
) async {
  final container = ProviderContainer(
    overrides: [
      expressionRepositoryProvider.overrideWithValue(repository),
      currentChildIdProvider.overrideWith((ref) => 4),
    ],
  );
  addTearDown(container.dispose);

  final router = GoRouter(
    initialLocation: '/expression',
    routes: [
      GoRoute(path: '/expression', builder: (_, _) => const ExpressionPage()),
    ],
  );
  addTearDown(router.dispose);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('403 显示年级限制且不伪装成空列表', (tester) async {
    final repository = FakeExpressionRepository()
      ..topicsError = ApiException('grade too low', statusCode: 403);

    await _pumpPage(tester, repository);

    expect(find.textContaining('三年级以上'), findsOneWidget);
    expect(find.textContaining('还没有可以讲的知识点'), findsNothing);
  });

  testWidgets('加载失败显示重试入口', (tester) async {
    final repository = FakeExpressionRepository()
      ..topicsError = ApiException('server error', statusCode: 500);

    await _pumpPage(tester, repository);

    expect(find.textContaining('没加载出来'), findsOneWidget);
    expect(find.text('重试'), findsOneWidget);
  });

  testWidgets('空主题显示先学一课提示', (tester) async {
    await _pumpPage(tester, FakeExpressionRepository());

    expect(find.textContaining('还没有可以讲的知识点'), findsOneWidget);
  });

  testWidgets('保存失败显示重试提示', (tester) async {
    final repository = FakeExpressionRepository()
      ..topicsResult = const [_topic]
      ..createNoteError = ApiException('server error', statusCode: 500);

    await _pumpPage(tester, repository);
    await tester.tap(find.text('比喻'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('expression-input')),
      '我讲一讲',
    );
    await tester.pump();
    await tester.tap(find.text('讲完了'));
    await tester.pumpAndSettle();

    expect(find.textContaining('没存上'), findsOneWidget);
    expect(find.text('讲完了'), findsOneWidget);
  });

  testWidgets('选择主题后显示表达输入框', (tester) async {
    final repository = FakeExpressionRepository()
      ..topicsResult = const [_topic];

    await _pumpPage(tester, repository);
    await tester.tap(find.text('比喻'));
    await tester.pump();

    expect(find.byKey(const ValueKey('expression-input')), findsOneWidget);
    expect(find.text('讲完了'), findsOneWidget);
  });
}
