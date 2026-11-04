import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/pdf_repository.dart';

class ReaderState {
  const ReaderState({
    this.documents = const AsyncLoading<List<PdfDoc>>(),
    this.lessons = const [],
    this.currentLesson,
    this.annotations = const [],
    this.busy = false,
  });

  final AsyncValue<List<PdfDoc>> documents;
  final List<PdfLesson> lessons;
  final PdfLesson? currentLesson;
  final List<AnnotationItem> annotations;
  final bool busy;

  ReaderState copyWith({
    AsyncValue<List<PdfDoc>>? documents,
    List<PdfLesson>? lessons,
    PdfLesson? Function()? currentLesson,
    List<AnnotationItem>? annotations,
    bool? busy,
  }) =>
      ReaderState(
        documents: documents ?? this.documents,
        lessons: lessons ?? this.lessons,
        currentLesson: currentLesson != null ? currentLesson() : this.currentLesson,
        annotations: annotations ?? this.annotations,
        busy: busy ?? this.busy,
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
    final result = await AsyncValue.guard(() => ref.read(pdfRepositoryProvider).documents());
    if (!ref.mounted) return;
    state = state.copyWith(documents: result);
  }

  Future<void> loadLessons(int documentId) async {
    final lessons = await ref.read(pdfRepositoryProvider).lessons(documentId);
    if (!ref.mounted) return;
    state = state.copyWith(lessons: lessons);
  }

  Future<void> openLesson(PdfLesson lesson) async {
    state = state.copyWith(currentLesson: () => lesson, annotations: const []);
    await loadAnnotations(lesson.id);
  }

  Future<void> loadAnnotations(int lessonId) async {
    final annotations = await ref.read(pdfRepositoryProvider).annotations(lessonId);
    if (!ref.mounted) return;
    state = state.copyWith(annotations: annotations);
  }

  /// 划词释义
  Future<String?> glossary(String quote) async {
    final lessonId = state.currentLesson?.id;
    final uid = _uid;
    if (lessonId == null) return null;
    state = state.copyWith(busy: true);
    String? meaning;
    try {
      meaning = await ref.read(pdfRepositoryProvider).glossary(lessonId: lessonId, quote: quote, userId: uid);
    } catch (_) {
      meaning = null;
    }
    if (!ref.mounted) return meaning;
    state = state.copyWith(busy: false);
    return meaning;
  }

  /// 添加笔记
  Future<void> addNote(String quote, String note) async {
    final lessonId = state.currentLesson?.id;
    final uid = _uid;
    if (lessonId == null) return;
    try {
      await ref.read(pdfRepositoryProvider).addNote(lessonId: lessonId, quote: quote, note: note, userId: uid);
    } catch (_) {}
    if (!ref.mounted) return;
    await loadAnnotations(lessonId);
  }
}

final readerControllerProvider = NotifierProvider<ReaderController, ReaderState>(ReaderController.new);
