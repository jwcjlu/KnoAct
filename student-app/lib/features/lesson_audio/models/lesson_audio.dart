class AudioMark {
  final String label;
  final double startSec;
  const AudioMark(this.label, this.startSec);
  factory AudioMark.fromJson(Map<String, dynamic> j) =>
      AudioMark(j['label'] as String? ?? '', (j['start_sec'] as num? ?? 0).toDouble());
}

class LessonAudio {
  final int id;
  final int? lessonId;
  final String unitLabel;
  final String audioPath;
  final List<AudioMark> marks;
  const LessonAudio({
    required this.id,
    this.lessonId,
    required this.unitLabel,
    required this.audioPath,
    required this.marks,
  });
  factory LessonAudio.fromJson(Map<String, dynamic> j) => LessonAudio(
        id: j['id'] as int,
        lessonId: j['lesson_id'] as int?,
        unitLabel: j['unit_label'] as String? ?? '',
        audioPath: j['audio_path'] as String? ?? '',
        marks: ((j['marks'] as List?) ?? [])
            .map((e) => AudioMark.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

String audioUrlForPath(String path, {required String base}) {
  final p = path.startsWith('/') ? path : '/$path';
  final b = base.endsWith('/') ? base.substring(0, base.length - 1) : base;
  return '$b$p';
}

double segmentStartFor(List<AudioMark> marks, double positionSec) {
  double start = 0;
  for (final m in marks) {
    if (m.startSec <= positionSec && m.startSec >= start) start = m.startSec;
  }
  return start;
}
