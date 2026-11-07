import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/reader/data/pdf_repository.dart';

void main() {
  test('PdfDoc parses storage_path', () {
    final d = PdfDoc.fromJson({
      'id': 1,
      'filename': 'a.pdf',
      'subject': '语文',
      'lesson_count': 3,
      'storage_path': 'uploads/1_a.pdf',
    });
    expect(d.storagePath, 'uploads/1_a.pdf');
  });

  test('AnnotationItem parses color, page_number, rects', () {
    final a = AnnotationItem.fromJson({
      'id': 10,
      'kind': 'highlight',
      'quote': '桂花雨',
      'note': '',
      'color': 'blue',
      'page_number': 5,
      'rects': '[[0.1,0.2,0.3,0.4]]',
    });
    expect(a.color, 'blue');
    expect(a.pageNumber, 5);
    expect(a.rects, '[[0.1,0.2,0.3,0.4]]');
  });

  test('AnnotationItem defaults when fields missing', () {
    final a = AnnotationItem.fromJson({
      'id': 1,
      'kind': 'underline',
      'quote': '雨',
      'note': '备注',
    });
    expect(a.color, 'yellow');
    expect(a.pageNumber, 1);
    expect(a.rects, '');
  });
}
