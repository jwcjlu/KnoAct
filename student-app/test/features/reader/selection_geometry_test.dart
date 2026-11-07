import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/reader/logic/selection_geometry.dart';

void main() {
  const page = Size(100, 200);

  test('empty input returns empty list', () {
    expect(normaliseRects([], page), isEmpty);
  });

  test('single rect normalises to 0-1', () {
    final out = normaliseRects(
      [const PageSelectionRect(left: 10, top: 20, width: 30, height: 10)],
      page,
    );
    expect(out.length, 1);
    expect(out[0][0], closeTo(0.1, 0.001));
    expect(out[0][1], closeTo(0.1, 0.001));
    expect(out[0][2], closeTo(0.4, 0.001));
    expect(out[0][3], closeTo(0.15, 0.001));
  });

  test('merges fragments on same line', () {
    final out = normaliseRects(
      [
        const PageSelectionRect(left: 10, top: 50, width: 20, height: 8),
        const PageSelectionRect(left: 35, top: 51, width: 25, height: 8),
      ],
      page,
    );
    expect(out.length, 1);
    expect(out[0][0], closeTo(0.1, 0.001));
    expect(out[0][2], closeTo(0.6, 0.001));
  });

  test('clamps rects outside page box', () {
    final out = normaliseRects(
      [const PageSelectionRect(left: -10, top: 0, width: 50, height: 10)],
      page,
    );
    expect(out[0][0], 0);
  });

  test('encodeRects round trip', () {
    final rects = [
      [0.1, 0.2, 0.5, 0.3],
    ];
    expect(decodeRects(encodeRects(rects)), rects);
  });
}
