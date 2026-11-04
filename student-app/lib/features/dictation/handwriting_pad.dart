import 'dart:convert';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

/// 手写画板：用手指/手写笔书写，可清空、导出为 PNG base64（供听写批改）。
class HandwritingPad extends StatefulWidget {
  const HandwritingPad({super.key, this.height = 220});

  final double height;

  @override
  State<HandwritingPad> createState() => HandwritingPadState();
}

class HandwritingPadState extends State<HandwritingPad> {
  final _strokes = <List<Offset>>[];
  final _current = <Offset>[];
  final _boundaryKey = GlobalKey();

  void _clear() {
    setState(() {
      _strokes.clear();
      _current.clear();
    });
  }

  /// 截取画板为 PNG 并返回 base64（不含 data: 前缀）；画板为空时返回空串
  Future<String> exportImage() async {
    if (_strokes.isEmpty && _current.isEmpty) return '';
    final boundary = _boundaryKey.currentContext?.findRenderObject() as RenderRepaintBoundary?;
    if (boundary == null) return '';
    final image = await boundary.toImage(pixelRatio: 3.0);
    final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
    if (byteData == null) return '';
    return base64Encode(Uint8List.view(byteData.buffer, byteData.offsetInBytes, byteData.lengthInBytes));
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Container(
        height: widget.height,
        width: double.infinity,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.grey.shade300),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: RepaintBoundary(
            key: _boundaryKey,
            child: GestureDetector(
              onPanStart: (d) => setState(() {
                _current.clear();
                _current.add(d.localPosition);
              }),
              onPanUpdate: (d) => setState(() => _current.add(d.localPosition)),
              onPanEnd: (_) => setState(() {
                if (_current.isNotEmpty) _strokes.add(List.of(_current));
                _current.clear();
              }),
              child: CustomPaint(
                painter: _HandwritingPainter(strokes: _strokes, current: _current),
                size: Size.infinite,
              ),
            ),
          ),
        ),
      ),
      const SizedBox(height: 8),
      Row(mainAxisAlignment: MainAxisAlignment.end, children: [
        TextButton.icon(onPressed: _clear, icon: const Icon(Icons.cleaning_services, size: 18), label: const Text('清空')),
      ]),
    ]);
  }
}

class _HandwritingPainter extends CustomPainter {
  _HandwritingPainter({required this.strokes, required this.current});

  final List<List<Offset>> strokes;
  final List<Offset> current;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.black
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;

    for (final stroke in strokes) {
      _drawStroke(canvas, stroke, paint);
    }
    if (current.isNotEmpty) {
      _drawStroke(canvas, current, paint);
    }
  }

  void _drawStroke(Canvas canvas, List<Offset> stroke, Paint paint) {
    if (stroke.length == 1) {
      canvas.drawPoints(ui.PointMode.points, stroke, paint..strokeWidth = 4);
      return;
    }
    final path = Path()..moveTo(stroke.first.dx, stroke.first.dy);
    for (var i = 1; i < stroke.length; i++) {
      path.lineTo(stroke[i].dx, stroke[i].dy);
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_HandwritingPainter oldDelegate) =>
      oldDelegate.strokes != strokes || oldDelegate.current != current;
}
