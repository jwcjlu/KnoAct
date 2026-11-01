import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/home/data/home_repository.dart';

class FakeApi implements ApiClient {
  final calls = <String>[];
  Object? postResult = {'ok': true};

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) => throw UnimplementedError();

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    calls.add('POST $path $body');
    return postResult;
  }

  @override
  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) =>
      throw UnimplementedError();
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
}
