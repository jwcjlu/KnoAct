import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../auth/session.dart';
import 'data/pdf_repository.dart';

const _kReaderDocId = 'knoact_reader_doc_id';
const _kReaderLessonId = 'knoact_reader_lesson_id';

class ReaderState {
  const ReaderState({
    this.documents = const AsyncLoading<List<PdfDoc>>(),
    this.lessons = const [],
    this.currentLesson,
    this.annotations = const [],
    this.busy = false,
    this.documentSubject = '语文',
    this.currentDocumentId,
    this.storagePath,
  });

  final AsyncValue<List<PdfDoc>> documents;
  final List<PdfLesson> lessons;
  final PdfLesson? currentLesson;
  final int? currentDocumentId;
  final String? storagePath;
  final List<AnnotationItem> annotations;
  final bool busy;

  /// 当前教材学科（作业出题 / 批改用）
  final String documentSubject;

  ReaderState copyWith({
    AsyncValue<List<PdfDoc>>? documents,
    List<PdfLesson>? lessons,
    PdfLesson? Function()? currentLesson,
    List<AnnotationItem>? annotations,
    bool? busy,
    String? documentSubject,
    int? Function()? currentDocumentId,
    String? Function()? storagePath,
  }) =>
      ReaderState(
        documents: documents ?? this.documents,
        lessons: lessons ?? this.lessons,
        currentLesson: currentLesson != null ? currentLesson() : this.currentLesson,
        annotations: annotations ?? this.annotations,
        busy: busy ?? this.busy,
        documentSubject: documentSubject ?? this.documentSubject,
        currentDocumentId: currentDocumentId != null ? currentDocumentId() : this.currentDocumentId,
        storagePath: storagePath != null ? storagePath() : this.storagePath,
      );
}

class ReaderController extends Notifier<ReaderState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  ReaderState build() {
    ref.watch(currentChildIdProvider);
    return const ReaderState();
  }

  Future<void> loadDocuments() async {
    state = state.copyWith(documents: const AsyncLoading());
    final uid = _uid;
    final result = await AsyncValue.guard(() => ref.read(pdfRepositoryProvider).documents(userId: uid));
    if (!ref.mounted) return;
    state = state.copyWith(documents: result);
  }

  String? _storagePathFor(int documentId) {
    final docs = state.documents.asData?.value;
    if (docs == null) return null;
    for (final d in docs) {
      if (d.id == documentId && d.storagePath.isNotEmpty) return d.storagePath;
    }
    return null;
  }

  Future<void> loadLessons(int documentId, {String subject = '语文'}) async {
    if (state.documents.asData?.value == null) {
      await loadDocuments();
    }
    final lessons = await ref.read(pdfRepositoryProvider).lessons(documentId);
    if (!ref.mounted) return;
    state = state.copyWith(
      lessons: lessons,
      documentSubject: subject,
      currentLesson: () => null,
      currentDocumentId: () => documentId,
      storagePath: () => _storagePathFor(documentId),
    );
  }

  Future<void> _persistLessonPointer(int documentId, int lessonId) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kReaderDocId, documentId);
    await p.setInt(_kReaderLessonId, lessonId);
  }

  Future<void> openLesson(PdfLesson lesson) async {
    state = state.copyWith(currentLesson: () => lesson, annotations: const []);
    final docId = state.currentDocumentId;
    if (docId != null) await _persistLessonPointer(docId, lesson.id);
    await loadAnnotations(lesson.id);
  }

  PdfLesson? _lessonById(int id) {
    for (final l in state.lessons) {
      if (l.id == id) return l;
    }
    return null;
  }

  /// 直达 `/reader/view` 或刷新页面时恢复课文（状态仅在内存，需从 API 拉回）
  Future<bool> prepareView({int? lessonIdHint}) async {
    if (state.currentLesson != null) return true;

    final prefs = await SharedPreferences.getInstance();
    final targetLessonId = lessonIdHint ?? prefs.getInt(_kReaderLessonId);
    final savedDocId = prefs.getInt(_kReaderDocId);

    Future<bool> openTarget(int lessonId) async {
      final lesson = _lessonById(lessonId);
      if (lesson == null) return false;
      await openLesson(lesson);
      return state.currentLesson != null;
    }

    if (targetLessonId != null) {
      if (_lessonById(targetLessonId) != null) {
        return openTarget(targetLessonId);
      }
      if (savedDocId != null) {
        final subject = _subjectForDoc(savedDocId);
        await loadLessons(savedDocId, subject: subject);
        if (_lessonById(targetLessonId) != null) return openTarget(targetLessonId);
      }
      await loadDocuments();
      final docs = state.documents.asData?.value ?? [];
      for (final d in docs) {
        await loadLessons(d.id, subject: d.subject);
        if (_lessonById(targetLessonId) != null) return openTarget(targetLessonId);
      }
    }

    // 无记录：第一本教材第一课
    await loadDocuments();
    final docs = state.documents.asData?.value;
    if (docs == null || docs.isEmpty) return false;
    await loadLessons(docs.first.id, subject: docs.first.subject);
    if (state.lessons.isEmpty) return false;
    await openLesson(state.lessons.first);
    return state.currentLesson != null;
  }

  String _subjectForDoc(int docId) {
    final docs = state.documents.asData?.value;
    if (docs == null) return state.documentSubject;
    for (final d in docs) {
      if (d.id == docId) return d.subject;
    }
    return state.documentSubject;
  }

  Future<void> loadAnnotations(int lessonId) async {
    final annotations = await ref.read(pdfRepositoryProvider).annotations(lessonId);
    if (!ref.mounted) return;
    state = state.copyWith(annotations: annotations);
  }

  /// 划词释义
  Future<String?> glossary(
    String quote, {
    int pageNumber = 1,
    String rects = '',
  }) async {
    final lessonId = state.currentLesson?.id;
    final uid = _uid;
    if (lessonId == null) return null;
    state = state.copyWith(busy: true);
    String? meaning;
    try {
      meaning = await ref.read(pdfRepositoryProvider).glossary(
            lessonId: lessonId,
            quote: quote,
            userId: uid,
            pageNumber: pageNumber,
            rects: rects,
          );
    } catch (_) {
      meaning = null;
    }
    if (!ref.mounted) return meaning;
    state = state.copyWith(busy: false);
    return meaning;
  }

  Future<void> addHighlight(
    String quote, {
    String kind = 'highlight',
    String color = 'yellow',
    int pageNumber = 1,
    String rects = '',
  }) async {
    final lessonId = state.currentLesson?.id;
    final uid = _uid;
    if (lessonId == null || quote.trim().isEmpty) return;
    try {
      await ref.read(pdfRepositoryProvider).addHighlight(
            lessonId: lessonId,
            quote: quote.trim(),
            kind: kind,
            userId: uid,
            color: color,
            pageNumber: pageNumber,
            rects: rects,
          );
    } catch (_) {}
    if (!ref.mounted) return;
    await loadAnnotations(lessonId);
  }

  /// 添加笔记
  Future<void> addNote(
    String quote,
    String note, {
    String color = 'yellow',
    int pageNumber = 1,
    String rects = '',
  }) async {
    final lessonId = state.currentLesson?.id;
    final uid = _uid;
    if (lessonId == null) return;
    try {
      await ref.read(pdfRepositoryProvider).addNote(
            lessonId: lessonId,
            quote: quote,
            note: note,
            userId: uid,
            color: color,
            pageNumber: pageNumber,
            rects: rects,
          );
    } catch (_) {}
    if (!ref.mounted) return;
    await loadAnnotations(lessonId);
  }
}

final readerControllerProvider = NotifierProvider<ReaderController, ReaderState>(ReaderController.new);
