import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';

class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.status, this.body, this.contentType);
  final int status;
  final List<int> body;
  final String contentType;
  RequestOptions? last;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    last = options;
    return ResponseBody.fromBytes(body, status, headers: {
      Headers.contentTypeHeader: [contentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

ApiClient _client(_FakeAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://api.test'));
  dio.httpClientAdapter = adapter;
  return ApiClient('http://api.test', dio: dio);
}

void main() {
  test('get 返回解析后的 JSON', () async {
    final a = _FakeAdapter(200, utf8.encode('{"balance": 35}'), 'application/json');
    final data = await _client(a).get('/api/points/balance', query: {'user_id': 4});
    expect(data, {'balance': 35});
    expect(a.last!.uri.toString(), 'http://api.test/api/points/balance?user_id=4');
  });

  test('非 2xx 抛出带状态码的 ApiException', () async {
    final a = _FakeAdapter(502, utf8.encode('<html>502 Bad Gateway</html>'), 'text/html');
    expect(
      () => _client(a).get('/api/home/snapshot'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 502)),
    );
  });

  test('getBytes 返回字节与 content-type', () async {
    final a = _FakeAdapter(200, [1, 2, 3], 'audio/mpeg');
    final r = await _client(a).getBytes('/api/tts/synthesize', query: {'text': 'hi'});
    expect(r.bytes, [1, 2, 3]);
    expect(r.contentType, 'audio/mpeg');
  });

  test('asMap / asList 对非预期结构抛 ApiException', () {
    expect(asMap({'a': 1}), {'a': 1});
    expect(asList([1]), [1]);
    expect(() => asMap('<html>'), throwsA(isA<ApiException>()));
    expect(() => asList({'a': 1}), throwsA(isA<ApiException>()));
  });
}
