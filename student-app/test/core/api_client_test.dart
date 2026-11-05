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

  ApiClient authed(_FakeAdapter a, {String? token, void Function()? onExpire}) {
    final dio = Dio(BaseOptions(baseUrl: 'http://api.test'));
    dio.httpClientAdapter = a;
    return ApiClient('http://api.test',
        dio: dio, accessToken: () async => token, onUnauthorized: () async => onExpire?.call());
  }

  test('有令牌时附带 Authorization Bearer，无令牌不带', () async {
    final a = _FakeAdapter(200, utf8.encode('{}'), 'application/json');
    await authed(a, token: 'abc').get('/api/auth/me');
    expect(a.last!.headers['Authorization'], 'Bearer abc');
    await authed(a).get('/api/auth/me');
    expect(a.last!.headers.containsKey('Authorization'), isFalse);
  });

  test('patch 发送 PATCH 请求体', () async {
    final a = _FakeAdapter(200, utf8.encode('{"ok":true}'), 'application/json');
    await authed(a, token: 't').patch('/api/auth/me/profile', body: {'display_name': 'x'});
    expect(a.last!.method, 'PATCH');
    expect(a.last!.data, {'display_name': 'x'});
  });

  test('受保护接口 401 触发 onUnauthorized 并带出错误码', () async {
    var expired = 0;
    final a = _FakeAdapter(401, utf8.encode('{"detail":{"error":"token_expired"}}'), 'application/json');
    await expectLater(
      authed(a, token: 'old', onExpire: () => expired++).get('/api/home/snapshot'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 401).having((e) => e.code, 'code', 'token_expired')),
    );
    expect(expired, 1);
  });

  test('登录接口的 401 是凭证错误，不清除会话', () async {
    var expired = 0;
    final a = _FakeAdapter(401, utf8.encode('{"detail":{"error":"invalid_credentials"}}'), 'application/json');
    await expectLater(
      authed(a, onExpire: () => expired++).post('/api/auth/login', body: {'login_name': 'a', 'password': 'b'}),
      throwsA(isA<ApiException>().having((e) => e.code, 'code', 'invalid_credentials')),
    );
    expect(expired, 0);
  });

  test('非 401 错误不清除会话', () async {
    var expired = 0;
    final a = _FakeAdapter(403, utf8.encode('{"detail":{"error":"parent_required"}}'), 'application/json');
    await expectLater(authed(a, token: 't', onExpire: () => expired++).get('/api/x'), throwsA(isA<ApiException>()));
    expect(expired, 0);
  });

  test('asMap / asList 对非预期结构抛 ApiException', () {
    expect(asMap({'a': 1}), {'a': 1});
    expect(asList([1]), [1]);
    expect(() => asMap('<html>'), throwsA(isA<ApiException>()));
    expect(() => asList({'a': 1}), throwsA(isA<ApiException>()));
  });
}
