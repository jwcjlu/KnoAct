import 'package:flutter/foundation.dart';

const bool _hasApiBase = bool.hasEnvironment('API_BASE');
const String _apiBase = String.fromEnvironment('API_BASE');
/// 本地 Web / 模拟器开发默认后端
const String localApiBase = 'http://127.0.0.1:8010';

/// 未配置 `--dart-define=API_BASE` 时，Android/iOS 安装包默认连此地址（ECS 对外入口，nginx 反代 /api、/uploads）
const String defaultProdApiBase = 'http://8.163.40.224:8082';

/// 本地 Web（localhost / 127.0.0.1 随机端口）加载教材页图时，与页面使用同一 host，
/// 避免 `localhost` 与 `127.0.0.1` 混用导致 Cookie / 行为不一致。
String devAssetBackendOrigin({Uri? pageUri}) {
  final u = pageUri ?? Uri.base;
  final h = u.host;
  if (h == 'localhost' || h == '127.0.0.1') {
    return '${u.scheme}://$h:8010';
  }
  return localApiBase;
}

/// 后端地址：未定义 API_BASE 时 Web 连本地后端、移动端连 [defaultProdApiBase]；空串时 Web 走同源。
String resolveApiBase({
  bool hasDefine = _hasApiBase,
  String defined = _apiBase,
  bool isWeb = kIsWeb,
  Uri? pageUri,
}) {
  if (!hasDefine) return isWeb ? localApiBase : defaultProdApiBase;
  if (defined.isNotEmpty) return defined;
  if (isWeb) return (pageUri ?? Uri.base).origin;
  return defaultProdApiBase;
}

/// 教材页图等静态资源用的 API 根。
///
/// [resolveApiBase] 在 Web 且 `API_BASE=""` 时取页面同源（生产由 nginx 反代 `/api` 与 `/uploads`）。
/// 本地 `flutter run -d chrome` 随机端口（如 :60372）并无 `/uploads`，此时尚用同源会导致
/// `CachedNetworkImage` 404 →「页面加载失败」；localhost / 127.0.0.1 且端口不是后端端口时
/// 改连 [localApiBase]。
///
/// [hasDefine] / [defined] / [isWeb] 与 [resolveApiBase] 对齐，便于单测覆盖编译期 `API_BASE`。
String apiBaseForAssets({
  Uri? pageUri,
  bool hasDefine = _hasApiBase,
  String defined = _apiBase,
  bool isWeb = kIsWeb,
}) {
  final u = pageUri ?? Uri.base;
  if (isWeb && hasDefine && defined.isEmpty) {
    final host = u.host;
    if (host == 'localhost' || host == '127.0.0.1') {
      const backendPort = 8010;
      final port = u.hasPort ? u.port : (u.scheme == 'https' ? 443 : 80);
      if (port != backendPort) {
        return devAssetBackendOrigin(pageUri: u);
      }
    }
  }
  return resolveApiBase(hasDefine: hasDefine, defined: defined, isWeb: isWeb, pageUri: pageUri);
}

/// 拼接静态资源 URL。后端多为 `uploads/...`（无前导 `/`），直接拼在 host 上会生成非法 URL。
String resolveApiAssetUrl(
  String path, {
  Uri? pageUri,
  bool hasDefine = _hasApiBase,
  String defined = _apiBase,
  bool isWeb = kIsWeb,
}) {
  if (path.isEmpty) {
    return apiBaseForAssets(pageUri: pageUri, hasDefine: hasDefine, defined: defined, isWeb: isWeb);
  }
  final base = apiBaseForAssets(pageUri: pageUri, hasDefine: hasDefine, defined: defined, isWeb: isWeb)
      .replaceAll(RegExp(r'/$'), '');
  final normalized = path.startsWith('/') ? path : '/$path';
  return '$base$normalized';
}
