import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/providers.dart';
import 'data/lesson_audio_repository.dart';
import 'models/lesson_audio.dart';

final lessonAudioRepositoryProvider = Provider<LessonAudioRepository>(
  (ref) => LessonAudioRepository(ref.read(apiClientProvider)),
);

final lessonAudioProvider =
    FutureProvider.family<List<LessonAudio>, int>((ref, docId) {
  return ref.read(lessonAudioRepositoryProvider).listByDocument(docId);
});
