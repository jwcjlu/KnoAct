import '../../../core/config.dart';

/// 静态 PDF / uploads 路径 → 可请求的完整 URL（中文路径分段编码）。
String encodedStorageUrl(String storagePath) {
  final base = apiBaseForAssets().replaceAll(RegExp(r'/$'), '');
  final normalized = storagePath.startsWith('/') ? storagePath.substring(1) : storagePath;
  final encodedPath = normalized.split('/').map(Uri.encodeComponent).join('/');
  return '$base/$encodedPath';
}
