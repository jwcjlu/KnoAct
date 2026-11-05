import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/center/data/center_repository.dart';

class FakeApi implements ApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);

  final calls = <String>[];
  Object? Function(String path, Map<String, dynamic>? query)? onGet;

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    calls.add('GET $path $query');
    return onGet!(path, query);
  }

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    calls.add('POST $path $body');
    return {'ok': true};
  }

  @override
  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) =>
      throw UnimplementedError();

  @override
  Future<Stream<List<int>>> postStream(String path, {Object? body}) => throw UnimplementedError();
}

void main() {
  test('阅读用语文快照的当前课；缺失时返回空材料且不请求阅读接口', () async {
    final api = FakeApi()
      ..onGet = (path, q) => path == '/api/home/snapshot'
          ? {'lesson_progress': {'current_lesson_id': null}}
          : throw StateError('should not request $path');
    final m = await CenterRepository(api).reading(4);
    expect(m.isEmpty, isTrue);
    expect(api.calls.single, contains('subject: 语文'));
  });

  test('阅读材料按当前课请求', () async {
    final api = FakeApi()
      ..onGet = (path, q) => path == '/api/home/snapshot'
          ? {'lesson_progress': {'current_lesson_id': 46}}
          : {'text': '课文', 'questions': [{'question': 'Q', 'answer': 'A'}]};
    final m = await CenterRepository(api).reading(4);
    expect(m.text, '课文');
    expect(api.calls.last, contains('lesson_id: 46'));
  });

  test('答错收录错题本', () async {
    final api = FakeApi();
    await CenterRepository(api).submitWrong(userId: 4, question: 'Q', yourAnswer: 'x', correctAnswer: 'A', sourceType: 'reading');
    expect(api.calls.single, startsWith('POST /api/review/submit'));
    expect(api.calls.single, contains('source_type: reading'));
  });
}
