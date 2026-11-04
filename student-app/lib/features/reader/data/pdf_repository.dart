import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

/// 教材
class PdfDoc {
  const PdfDoc({required this.id, required this.filename, required this.subject, required this.lessonCount});

  factory PdfDoc.fromJson(Map<String, dynamic> j) => PdfDoc(
        id: (j['id'] as num).toInt(),
        filename: '${j['filename'] ?? ''}',
        subject: '${j['subject'] ?? ''}',
        lessonCount: (j['lesson_count'] as num?)?.toInt() ?? 0,
      );

  final int id;
  final String filename;
  final String subject;
  final int lessonCount;
}

/// 一课（含页面图片 + 课文文本）
class PdfLesson {
  const PdfLesson({
    required this.id,
    required this.title,
    required this.startPage,
    required this.endPage,
    required this.texts,
    required this.pages,
    this.documentVersion = 0,
  });

  factory PdfLesson.fromJson(Map<String, dynamic> j) => PdfLesson(
        id: (j['id'] as num).toInt(),
        title: '${j['title'] ?? ''}',
        startPage: (j['start_page'] as num?)?.toInt() ?? 1,
        endPage: (j['end_page'] as num?)?.toInt() ?? 1,
        texts: [if (j['texts'] is List) for (final t in (j['texts'] as List)) '$t'],
        pages: [
          if (j['pages'] is List)
            for (final p in (j['pages'] as List).whereType<Map>())
              PdfPage(
                pageNumber: (p['page_number'] as num?)?.toInt() ?? 0,
                imagePath: '${p['image_path'] ?? ''}',
              ),
        ],
        documentVersion: (j['document_version'] as num?)?.toInt() ?? 0,
      );

  final int id;
  final String title;
  final int startPage;
  final int endPage;
  final List<String> texts;
  final List<PdfPage> pages;
  final int documentVersion;

  /// 课文全文（合并所有 text）
  String get fullText => texts.join('\n');
}

class PdfPage {
  const PdfPage({required this.pageNumber, required this.imagePath});

  final int pageNumber;
  final String imagePath;
}

/// 标注
class AnnotationItem {
  const AnnotationItem({required this.id, required this.kind, required this.quote, required this.note});

  factory AnnotationItem.fromJson(Map<String, dynamic> j) => AnnotationItem(
        id: (j['id'] as num).toInt(),
        kind: '${j['kind'] ?? ''}',
        quote: '${j['quote'] ?? ''}',
        note: '${j['note'] ?? ''}',
      );

  final int id;
  final String kind; // highlight | underline | note | glossary
  final String quote;
  final String note;
}

class PdfRepository {
  PdfRepository(this._api);

  final ApiClient _api;

  Future<List<PdfDoc>> documents({int? userId}) async {
    final list = await _api.get('/api/pdf/documents',
        query: userId != null ? {'user_id': userId} : null);
    return [for (final d in (list as List).whereType<Map>()) PdfDoc.fromJson(Map<String, dynamic>.from(d))];
  }

  Future<List<PdfLesson>> lessons(int documentId) async {
    final list = await _api.get('/api/pdf/documents/$documentId/lessons');
    return [for (final l in (list as List).whereType<Map>()) PdfLesson.fromJson(Map<String, dynamic>.from(l))];
  }

  Future<List<AnnotationItem>> annotations(int lessonId) async {
    final list = await _api.get('/api/annotations', query: {'lesson_id': lessonId});
    return [for (final a in (list as List).whereType<Map>()) AnnotationItem.fromJson(Map<String, dynamic>.from(a))];
  }

  /// 划词释义：选中词 → AI 查释义（落库为 glossary 标注）
  Future<String> glossary({required int lessonId, required String quote, int? userId}) async {
    final r = asMap(await _api.post('/api/annotations/glossary', body: {
      'lesson_id': lessonId,
      'quote': quote,
      'user_id': ?userId,
    }));
    return '${r['note'] ?? ''}';
  }

  /// 添加笔记
  Future<void> addNote({required int lessonId, required String quote, required String note, int? userId}) async {
    await _api.post('/api/annotations', body: {
      'lesson_id': lessonId,
      'kind': 'note',
      'quote': quote,
      'note': note,
      'user_id': ?userId,
    });
  }
}

final pdfRepositoryProvider = Provider<PdfRepository>((ref) => PdfRepository(ref.watch(apiClientProvider)));
