import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/home/data/home_repository.dart';

class FakeApi implements ApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);

  final calls = <String>[];
  Object? postResult = {'ok': true};
  Object? Function(String path, Map<String, dynamic>? query)? onGet;

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    calls.add('GET $path $query');
    return onGet!(path, query);
  }

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    calls.add('POST $path $body');
    return postResult;
  }

  @override
  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) =>
      throw UnimplementedError();

  @override
  Future<Stream<List<int>>> postStream(String path, {Object? body}) => throw UnimplementedError();
}

void main() {
  test('提交任务：后端 ok:true 视为成功', () async {
    final api = FakeApi();
    await HomeRepository(api).submitTask(7);
    expect(api.calls.single, startsWith('POST /api/tasks/7/submit'));
  });

  test('提交任务：后端 ok:false（任务已删除等）视为失败', () async {
    final api = FakeApi()..postResult = {'ok': false};
    await expectLater(HomeRepository(api).submitTask(7), throwsA(isA<ApiException>()));
  });

  test('balance 传 bucketId 时加入 bucket_id 查询参数', () async {
    final api = FakeApi()..onGet = (_, _) => {'balance': 120};
    final balance = await HomeRepository(api).balance(4, bucketId: 3);
    expect(balance, 120);
    expect(api.calls.single, contains('bucket_id: 3'));
    expect(api.calls.single, contains('user_id: 4'));
  });

  test('balance 不传 bucketId 时不带 bucket_id 参数', () async {
    final api = FakeApi()..onGet = (_, _) => {'balance': 120};
    await HomeRepository(api).balance(4);
    expect(api.calls.single, isNot(contains('bucket_id')));
  });

  test('buckets 解析 {id, grade, school_year, status}', () async {
    final api = FakeApi()
      ..onGet = (_, _) => [
            {'id': 2, 'grade': 3, 'school_year': '2025-2026', 'status': 'archived'},
            {'id': 9, 'grade': 4, 'school_year': '2026-2027', 'status': 'active'},
          ];
    final buckets = await HomeRepository(api).buckets(4);
    expect(buckets.length, 2);
    expect(buckets[0].id, 2);
    expect(buckets[0].grade, 3);
    expect(buckets[0].schoolYear, '2025-2026');
    expect(buckets[0].isActive, isFalse);
    expect(buckets[1].id, 9);
    expect(buckets[1].isActive, isTrue);
    expect(api.calls.single, contains('user_id: 4'));
  });
}
