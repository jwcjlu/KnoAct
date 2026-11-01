import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/home/data/home_models.dart';

void main() {
  test('HomeSnapshot 解析快照', () {
    final s = HomeSnapshot.fromJson({
      'user_name': '金同学',
      'points': 35,
      'lesson_progress': {'current': 3, 'total': 8, 'mastered': 2, 'current_lesson_id': 46},
    });
    expect(s.userName, '金同学');
    expect(s.lessonProgress.current, 3);
    expect(s.lessonProgress.total, 8);
    expect(s.lessonProgress.mastered, 2);
    expect(s.lessonProgress.currentLessonId, 46);
  });

  test('HomeSnapshot 缺字段时给默认值', () {
    final s = HomeSnapshot.fromJson({});
    expect(s.userName, '同学');
    expect(s.lessonProgress.current, 1);
    expect(s.lessonProgress.total, 0);
    expect(s.lessonProgress.currentLessonId, isNull);
  });

  test('StudyTask 解析任务', () {
    final t = StudyTask.fromJson({
      'id': 85, 'subject': '语文', 'task_type': 'reading', 'title': '桂花雨 阅读理解',
      'detail': null, 'points': 20, 'submit_status': 'not_started',
    });
    expect(t.id, 85);
    expect(t.subject, '语文');
    expect(t.taskType, 'reading');
    expect(t.detail, '');
    expect(t.points, 20);
    expect(t.submitStatus, 'not_started');
  });
}
