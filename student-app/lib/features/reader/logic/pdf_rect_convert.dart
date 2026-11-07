import 'package:pdfrx/pdfrx.dart';

import 'selection_geometry.dart';

/// PDF 坐标（原点左下）→ 页内顶左像素矩形。
PageSelectionRect pdfRectToTopLeft(PdfRect r, double pageW, double pageH) {
  return PageSelectionRect(
    left: r.left,
    top: pageH - r.top,
    width: r.width,
    height: r.top - r.bottom,
  );
}
