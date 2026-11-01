import 'package:flutter/foundation.dart';

const bool _hasApiBase = bool.hasEnvironment('API_BASE');
const String _apiBase = String.fromEnvironment('API_BASE');
const String localApiBase = 'http://127.0.0.1:8010';

/// 后端地址：未定义 API_BASE 时连本地开发后端；定义为空串时 Web 走同源（经 nginx 反代）。
String resolveApiBase({
  bool hasDefine = _hasApiBase,
  String defined = _apiBase,
  bool isWeb = kIsWeb,
  Uri? pageUri,
}) {
  if (!hasDefine) return localApiBase;
  if (defined.isNotEmpty) return defined;
  if (isWeb) return (pageUri ?? Uri.base).origin;
  return localApiBase;
}
