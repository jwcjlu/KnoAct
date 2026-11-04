import 'package:dio/dio.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

Map<String, dynamic> asMap(Object? data) {
  if (data is Map) return Map<String, dynamic>.from(data);
  throw ApiException('响应格式错误');
}

List<dynamic> asList(Object? data) {
  if (data is List) return data;
  throw ApiException('响应格式错误');
}

class ApiClient {
  ApiClient(String baseUrl, {Dio? dio})
      : _dio = dio ??
            Dio(BaseOptions(
              baseUrl: baseUrl,
              connectTimeout: const Duration(seconds: 10),
              // 听力/阅读材料与 TTS 可能当场调用大模型生成
              receiveTimeout: const Duration(seconds: 120),
            ));

  final Dio _dio;

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      _send(() => _dio.get<dynamic>(path, queryParameters: query));

  Future<dynamic> post(String path, {Object? body}) => _send(() => _dio.post<dynamic>(path, data: body));

  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) async {
    try {
      final r = await _dio.get<List<int>>(
        path,
        queryParameters: query,
        options: Options(responseType: ResponseType.bytes),
      );
      return (bytes: r.data ?? const <int>[], contentType: r.headers.value(Headers.contentTypeHeader) ?? '');
    } on DioException catch (e) {
      throw _wrap(e);
    }
  }

  /// POST 并返回 SSE 字节流（用于 /api/ask/stream 等流式端点）
  Future<Stream<List<int>>> postStream(String path, {Object? body}) async {
    try {
      final r = await _dio.post<ResponseBody>(
        path,
        data: body,
        options: Options(responseType: ResponseType.stream, headers: {'Accept': 'text/event-stream'}),
      );
      return r.data?.stream ?? const Stream.empty();
    } on DioException catch (e) {
      throw _wrap(e);
    }
  }

  Future<dynamic> _send(Future<Response<dynamic>> Function() call) async {
    try {
      return (await call()).data;
    } on DioException catch (e) {
      throw _wrap(e);
    }
  }

  ApiException _wrap(DioException e) =>
      ApiException(e.message ?? e.type.name, statusCode: e.response?.statusCode);
}
