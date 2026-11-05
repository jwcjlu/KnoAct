import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/wrongbook/data/wrongbook_repository.dart';

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
  test('list 传 bucket_id 时加入查询参数', () async {
    final api = FakeApi()..onGet = (_, _) => [];
    await WrongbookRepository(api).list(4, subject: '语文', bucketId: 12);
    expect(api.calls.single, contains('bucket_id: 12'));
    expect(api.calls.single, contains('subject: 语文'));
  });

  test('list 不传 bucket_id 时不带该参数', () async {
    final api = FakeApi()..onGet = (_, _) => [];
    await WrongbookRepository(api).list(4);
    expect(api.calls.single, isNot(contains('bucket_id')));
  });

  test('buckets 解析 {id, grade, school_year, status}', () async {
    final api = FakeApi()
      ..onGet = (_, _) => [
            {'id': 2, 'grade': 3, 'school_year': '2025-2026', 'status': 'archived'},
            {'id': 9, 'grade': 4, 'school_year': '2026-2027', 'status': 'active'},
          ];
    final buckets = await WrongbookRepository(api).buckets(4);
    expect(buckets.length, 2);
    expect(buckets[0].id, 2);
    expect(buckets[0].grade, 3);
    expect(buckets[0].schoolYear, '2025-2026');
    expect(buckets[0].isActive, isFalse);
    expect(buckets[1].id, 9);
    expect(buckets[1].grade, 4);
    expect(buckets[1].isActive, isTrue);
    expect(api.calls.single, contains('user_id: 4'));
  });
}
