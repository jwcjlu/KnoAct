import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/expression/data/expression_repository.dart';
import 'package:student_app/features/expression/expression_controller.dart';

const _topic = ExpressionTopic(
  kind: 'knowledge_point',
  id: 7,
  title: '比喻',
);

class FakeExpressionRepository extends ExpressionRepository {
  FakeExpressionRepository()
      : super(ApiClient('http://test.invalid'));

  Object? topicsError;
  List<ExpressionTopic> topicsResult = const [];
  int createNoteCalls = 0;

  @override
  Future<List<ExpressionTopic>> topics({required int userId}) async {
    final err = topicsError;
    if (err != null) throw err;
    return topicsResult;
  }

  @override
  Future<void> createNote({
    required int userId,
    int? knowledgePointId,
    int? itemId,
    required String text,
  }) async {
    createNoteCalls++;
    assertExpressionNoteTarget(
      knowledgePointId: knowledgePointId,
      itemId: itemId,
    );
  }
}

ProviderContainer _container(FakeExpressionRepository repo) {
  return ProviderContainer(overrides: [
    expressionRepositoryProvider.overrideWithValue(repo),
    currentChildIdProvider.overrideWith((ref) => 4),
  ]);
}

void main() {
  group('assertExpressionNoteTarget / createNote guard', () {
    final repo = ExpressionRepository(ApiClient('http://test.invalid'));

    test('neither id throws ArgumentError', () {
      expect(
        () => repo.createNote(userId: 1, text: '讲一讲'),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('both ids throws ArgumentError', () {
      expect(
        () => repo.createNote(
          userId: 1,
          knowledgePointId: 2,
          itemId: 3,
          text: '讲一讲',
        ),
        throwsA(isA<ArgumentError>()),
      );
    });
  });

  group('ExpressionController', () {
    test('submit with empty or whitespace does not call repository', () async {
      final repo = FakeExpressionRepository();
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('   ');
      await ctl.submit();

      expect(repo.createNoteCalls, 0);
      expect(container.read(expressionControllerProvider).done, isFalse);
    });

    test('successful submit sets done', () async {
      final repo = FakeExpressionRepository();
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('我这样理解的');
      await ctl.submit();

      expect(repo.createNoteCalls, 1);
      final s = container.read(expressionControllerProvider);
      expect(s.done, isTrue);
      expect(s.text, '我这样理解的');
    });

    test('loadTopics 403 sets forbidden and empty topics', () async {
      final repo = FakeExpressionRepository()
        ..topicsError = ApiException('grade too low', statusCode: 403);
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      await ctl.loadTopics();

      final s = container.read(expressionControllerProvider);
      expect(s.error, 'forbidden');
      expect(s.topics, isEmpty);
    });

    test('loadTopics other error sets failed', () async {
      final repo = FakeExpressionRepository()
        ..topicsError = ApiException('server error', statusCode: 500);
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      await ctl.loadTopics();

      expect(container.read(expressionControllerProvider).error, 'failed');
    });

    test('again clears selected text done keeps topics', () async {
      final repo = FakeExpressionRepository()..topicsResult = const [_topic];
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      await ctl.loadTopics();
      ctl.select(_topic);
      ctl.setText('我讲完了');
      await ctl.submit();
      expect(container.read(expressionControllerProvider).done, isTrue);

      ctl.again();
      final s = container.read(expressionControllerProvider);
      expect(s.topics, [_topic]);
      expect(s.selected, isNull);
      expect(s.text, '');
      expect(s.done, isFalse);
    });
  });
}