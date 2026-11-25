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
  Object? createNoteError;
  Object? probeError;
  List<ExpressionTopic> topicsResult = const [];
  int createNoteCalls = 0;
  int probeCalls = 0;
  ProbeResult nextProbeResult = const ProbeResult(
    done: false,
    question: '问一问？',
  );
  List<Map<String, String>>? lastCreateProbeTurns;

  @override
  Future<List<ExpressionTopic>> topics({required int userId}) async {
    final err = topicsError;
    if (err != null) throw err;
    return topicsResult;
  }

  @override
  Future<ProbeResult> probe({
    required int userId,
    int? knowledgePointId,
    int? itemId,
    required String text,
    required List<Map<String, String>> turns,
  }) async {
    probeCalls++;
    assertExpressionNoteTarget(
      knowledgePointId: knowledgePointId,
      itemId: itemId,
    );
    final err = probeError;
    if (err != null) throw err;
    return nextProbeResult;
  }

  @override
  Future<void> createNote({
    required int userId,
    int? knowledgePointId,
    int? itemId,
    required String text,
    List<Map<String, String>>? probeTurns,
  }) async {
    createNoteCalls++;
    lastCreateProbeTurns = probeTurns;
    assertExpressionNoteTarget(
      knowledgePointId: knowledgePointId,
      itemId: itemId,
    );
    final err = createNoteError;
    if (err != null) throw err;
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

    test('submit failure keeps text and sets submitError', () async {
      final repo = FakeExpressionRepository()
        ..createNoteError = ApiException('server error', statusCode: 500);
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      const draft = '我这样理解的';
      ctl.setText(draft);
      await ctl.submit();

      final s = container.read(expressionControllerProvider);
      expect(s.busy, isFalse);
      expect(s.submitError, 'failed');
      expect(s.done, isFalse);
      expect(s.text, draft);
    });

    test('retry after submit failure succeeds', () async {
      final repo = FakeExpressionRepository()
        ..createNoteError = ApiException('server error', statusCode: 500);
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('我讲一讲');
      await ctl.submit();
      expect(container.read(expressionControllerProvider).submitError, 'failed');

      repo.createNoteError = null;
      await ctl.submit();

      final s = container.read(expressionControllerProvider);
      expect(s.done, isTrue);
      expect(s.submitError, isNull);
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

    test('openProbe with empty text does not call probe', () async {
      final repo = FakeExpressionRepository();
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('   ');
      await ctl.openProbe();

      expect(repo.probeCalls, 0);
      expect(container.read(expressionControllerProvider).probeOpen, isFalse);
    });

    test('after 3 answers no further probe API calls', () async {
      final repo = FakeExpressionRepository()
        ..nextProbeResult = const ProbeResult(
          done: false,
          question: '第二问？',
        );
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('我讲一讲比喻');
      await ctl.openProbe();
      expect(repo.probeCalls, 1);

      await ctl.answerProbe('答一');
      expect(repo.probeCalls, 2);

      repo.nextProbeResult = const ProbeResult(
        done: false,
        question: '第三问？',
      );
      await ctl.answerProbe('答二');
      expect(repo.probeCalls, 3);

      await ctl.answerProbe('答三');
      expect(repo.probeCalls, 3);
      final s = container.read(expressionControllerProvider);
      expect(s.probeDone, isTrue);
      expect(s.probeTurns.length, 3);
    });

    test('submit includes probeTurns when present', () async {
      final repo = FakeExpressionRepository();
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('终稿内容');
      await ctl.openProbe();
      await ctl.answerProbe('我的回答');

      await ctl.submit();

      expect(repo.createNoteCalls, 1);
      expect(repo.lastCreateProbeTurns, [
        {'q': '问一问？', 'a': '我的回答'},
      ]);
    });

    test('probe failure sets probeError but submit can still succeed', () async {
      final repo = FakeExpressionRepository()
        ..probeError = ApiException('unavailable', statusCode: 503);
      final container = _container(repo);
      addTearDown(container.dispose);

      final ctl = container.read(expressionControllerProvider.notifier);
      ctl.select(_topic);
      ctl.setText('讲完了');
      await ctl.openProbe();

      expect(container.read(expressionControllerProvider).probeError, 'unavailable');

      repo.probeError = null;
      await ctl.submit();

      expect(repo.createNoteCalls, 1);
      final s = container.read(expressionControllerProvider);
      expect(s.done, isTrue);
      expect(repo.lastCreateProbeTurns, isNull);
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