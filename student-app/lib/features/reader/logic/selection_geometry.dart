import 'dart:convert';
import 'dart:ui';

/// 选区矩形（页内像素坐标，相对单页左上角）。
class PageSelectionRect {
  const PageSelectionRect({required this.left, required this.top, required this.width, required this.height});

  final double left;
  final double top;
  final double width;
  final double height;
}

/// 将页内像素矩形归一化到 0~1（对齐 Web `normaliseRects`：按行合并 + clamp）。
List<List<double>> normaliseRects(List<PageSelectionRect> clientRects, Size pageSize) {
  const minSize = 2.0;
  const overlapRatio = 0.5;
  double clamp(double v) => v.isFinite ? v.clamp(0.0, 1.0) : 0.0;

  if (pageSize.width <= 0 || pageSize.height <= 0) return [];

  final usable = <PageSelectionRect>[];
  for (final r in clientRects) {
    if (r.width >= minSize && r.height >= minSize) usable.add(r);
  }
  if (usable.isEmpty) return [];

  usable.sort((a, b) {
    final c = a.top.compareTo(b.top);
    return c != 0 ? c : a.left.compareTo(b.left);
  });

  final lines = <List<PageSelectionRect>>[];
  for (final r in usable) {
    List<PageSelectionRect>? line;
    for (final candidate in lines) {
      final p = candidate.first;
      final overlap = (p.top + p.height < r.top + r.height ? p.top + p.height : r.top + r.height) -
          (p.top > r.top ? p.top : r.top);
      final shorter = p.height < r.height ? p.height : r.height;
      if (shorter > 0 && overlap / shorter >= overlapRatio) {
        line = candidate;
        break;
      }
    }
    if (line != null) {
      line.add(r);
    } else {
      lines.add([r]);
    }
  }

  final merged = <PageSelectionRect>[];
  for (final line in lines) {
    var left = line.first.left;
    var top = line.first.top;
    var right = line.first.left + line.first.width;
    var bottom = line.first.top + line.first.height;
    for (final r in line) {
      left = left < r.left ? left : r.left;
      top = top < r.top ? top : r.top;
      final rr = r.left + r.width;
      final bb = r.top + r.height;
      right = right > rr ? right : rr;
      bottom = bottom > bb ? bottom : bb;
    }
    merged.add(PageSelectionRect(left: left, top: top, width: right - left, height: bottom - top));
  }

  final out = <List<double>>[];
  for (final r in merged) {
    final x0 = clamp(r.left / pageSize.width);
    final y0 = clamp(r.top / pageSize.height);
    final x1 = clamp((r.left + r.width) / pageSize.width);
    final y1 = clamp((r.top + r.height) / pageSize.height);
    if (x1 - x0 > 0.001 && y1 - y0 > 0.001) {
      out.add([x0 < x1 ? x0 : x1, y0 < y1 ? y0 : y1, x0 > x1 ? x0 : x1, y0 > y1 ? y0 : y1]);
    }
  }
  return out;
}

String encodeRects(List<List<double>> rects) => jsonEncode(rects);

List<List<double>> decodeRects(String json) {
  if (json.trim().isEmpty) return [];
  final decoded = jsonDecode(json);
  if (decoded is! List) return [];
  return [
    for (final row in decoded)
      if (row is List && row.length >= 4)
        [for (final v in row.take(4)) (v as num).toDouble()],
  ];
}
