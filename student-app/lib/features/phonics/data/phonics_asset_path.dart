/// Map catalog audio path → [AssetSource] path (no leading `assets/`).
String phonicsAssetSourcePath(String catalogPath) {
  var p = catalogPath.trim();
  if (p.isEmpty) return '';
  if (p.startsWith('assets/')) {
    p = p.substring('assets/'.length);
  }
  return p;
}
