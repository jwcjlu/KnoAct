import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/lesson_audio/models/lesson_audio.dart';

void main() {
  test('audioUrl 用 audio_path 拼 base', () {
    expect(
      audioUrlForPath('uploads/audio/1_x.mp3', base: 'http://127.0.0.1:8010'),
      'http://127.0.0.1:8010/uploads/audio/1_x.mp3',
    );
    expect(
      audioUrlForPath('/uploads/audio/1_x.mp3', base: 'http://127.0.0.1:8010/'),
      'http://127.0.0.1:8010/uploads/audio/1_x.mp3',
    );
  });

  test('segmentStartFor 返回最近起点，无 marks 返回 0', () {
    final marks = [const AudioMark('A', 10.0), const AudioMark('B', 25.0)];
    expect(segmentStartFor(marks, 15.0), 10.0);
    expect(segmentStartFor(marks, 30.0), 25.0);
    expect(segmentStartFor(marks, 5.0), 0.0);
    expect(segmentStartFor(const [], 5.0), 0.0);
  });

  test('LessonAudio.fromJson 解析 marks', () {
    final a = LessonAudio.fromJson({
      'id': 1, 'lesson_id': 3, 'unit_label': 'Unit 1',
      'audio_path': 'uploads/audio/x.mp3',
      'marks': [{'label': 'A', 'start_sec': 12.5}],
    });
    expect(a.unitLabel, 'Unit 1');
    expect(a.lessonId, 3);
    expect(a.marks.single.startSec, 12.5);
  });

  test('splitAudioRows 把 Word list 拆到单词表组', () {
    final rows = [
      LessonAudio(id: 1, lessonId: 54, unitLabel: 'Unit 1', audioPath: 'a', marks: const []),
      LessonAudio(id: 2, lessonId: null, unitLabel: 'Word list', audioPath: 'b', marks: const []),
      LessonAudio(id: 3, lessonId: 56, unitLabel: 'Unit 3', audioPath: 'c', marks: const []),
    ];
    final (unit, wordList) = splitAudioRows(rows);
    expect(unit.map((a) => a.unitLabel).toList(), ['Unit 1', 'Unit 3']);
    expect(wordList.map((a) => a.unitLabel).toList(), ['Word list']);
  });

  test('splitAudioRows 无单词表时 wordList 为空', () {
    final rows = [
      LessonAudio(id: 1, lessonId: 54, unitLabel: 'Unit 1', audioPath: 'a', marks: const []),
    ];
    final (unit, wordList) = splitAudioRows(rows);
    expect(unit.length, 1);
    expect(wordList, isEmpty);
  });
}
