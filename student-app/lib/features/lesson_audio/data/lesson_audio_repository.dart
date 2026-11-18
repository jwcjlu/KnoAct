import '../../../core/api_client.dart';
import '../../../core/config.dart';
import '../models/lesson_audio.dart';

class LessonAudioRepository {
  LessonAudioRepository(this._api);
  final ApiClient _api;

  Future<List<LessonAudio>> listByDocument(int documentId) async {
    final data = await _api.get('/api/lesson-audio', query: {'document_id': documentId});
    return (data as List)
        .map((e) => LessonAudio.fromJson(asMap(e)))
        .toList();
  }

  String audioUrl(String path) => audioUrlForPath(path, base: apiBaseForAssets());
}
