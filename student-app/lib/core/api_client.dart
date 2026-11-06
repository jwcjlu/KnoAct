import 'package:dio/dio.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.code});

  final String message;
  final int? statusCode;

  /// 后端 `detail.error` 业务错误码（如 `invalid_credentials`、`login_name_taken`）
  final String? code;

  @override
  String toString() => 'ApiException($statusCode${code == null ? '' : ', $code'}): $message';
}

Map<String, dynamic> asMap(Object? data) {
  if (data is Map) return Map<String, dynamic>.from(data);
  throw ApiException('响应格式错误');
}

List<dynamic> asList(Object? data) {
  if (data is List) return data;
  throw ApiException('响应格式错误');
}

/// 登录/注册/OTP 等「换取令牌」端点：401/4xx 是业务失败，不代表已有会话失效
bool _isCredentialEndpoint(String path) =>
    path.startsWith('/api/auth/login') ||
    path.startsWith('/api/auth/register') ||
    path.startsWith('/api/auth/otp/') ||
    path.startsWith('/api/auth/refresh') ||
    path.startsWith('/api/auth/password/');

class ApiClient {
  /// [accessToken] 在每次请求前读取，非空则附带 `Authorization: Bearer`；
  /// 非凭证端点返回 401 时调用 [onUnauthorized]（用于清除会话）。
  ApiClient(
    String baseUrl, {
    Dio? dio,
    Future<String?> Function()? accessToken,
    Future<void> Function()? onUnauthorized,
  }) : _dio = dio ??
            Dio(BaseOptions(
              baseUrl: baseUrl,
              connectTimeout: const Duration(seconds: 10),
              // 听力/阅读材料与 TTS 可能当场调用大模型生成
              receiveTimeout: const Duration(seconds: 120),
            )) {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        if (accessToken != null && !options.headers.containsKey('Authorization')) {
          final token = await accessToken();
          if (token != null && token.isNotEmpty) options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (e, handler) async {
        if (e.response?.statusCode == 401 && onUnauthorized != null && !_isCredentialEndpoint(e.requestOptions.path)) {
          await onUnauthorized();
        }
        handler.next(e);
      },
    ));
  }

  final Dio _dio;

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      _send(() => _dio.get<dynamic>(path, queryParameters: query));

  Future<dynamic> post(String path, {Object? body}) => _send(() => _dio.post<dynamic>(path, data: body));

  Future<dynamic> patch(String path, {Object? body}) => _send(() => _dio.patch<dynamic>(path, data: body));

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

  ApiException _wrap(DioException e) {
    final code = _errorCode(e.response?.data);
    final msg = _errorMessage(e.response?.data) ?? e.message ?? e.type.name;
    return ApiException(msg, statusCode: e.response?.statusCode, code: code);
  }

  static String? _errorCode(Object? data) {
    if (data is Map) {
      final detail = data['detail'];
      if (detail is Map && detail['error'] is String) return detail['error'] as String;
      if (detail is String) return detail;
    }
    return null;
  }

  static String? _errorMessage(Object? data) {
    if (data is Map) {
      final detail = data['detail'];
      if (detail is Map && detail['message'] is String) return detail['message'] as String;
      if (detail is String) return detail;
    }
    return null;
  }
}
