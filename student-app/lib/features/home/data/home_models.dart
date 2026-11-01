int _int(Object? v, int fallback) => v is num ? v.toInt() : fallback;

class LessonProgress {
  const LessonProgress({required this.current, required this.total, required this.mastered, this.currentLessonId});

  factory LessonProgress.fromJson(Map<String, dynamic> j) => LessonProgress(
        current: _int(j['current'], 1),
        total: _int(j['total'], 0),
        mastered: _int(j['mastered'], 0),
        currentLessonId: j['current_lesson_id'] is num ? (j['current_lesson_id'] as num).toInt() : null,
      );

  final int current;
  final int total;
  final int mastered;
  final int? currentLessonId;
}

class HomeSnapshot {
  const HomeSnapshot({required this.userName, required this.lessonProgress});

  factory HomeSnapshot.fromJson(Map<String, dynamic> j) {
    final lp = j['lesson_progress'];
    final name = j['user_name'];
    return HomeSnapshot(
      userName: name is String && name.isNotEmpty ? name : '同学',
      lessonProgress: LessonProgress.fromJson(lp is Map ? Map<String, dynamic>.from(lp) : const {}),
    );
  }

  final String userName;
  final LessonProgress lessonProgress;
}

class StudyTask {
  const StudyTask({
    required this.id,
    required this.subject,
    required this.taskType,
    required this.title,
    required this.detail,
    required this.points,
    required this.submitStatus,
  });

  factory StudyTask.fromJson(Map<String, dynamic> j) => StudyTask(
        id: _int(j['id'], 0),
        subject: (j['subject'] as String?) ?? '',
        taskType: (j['task_type'] as String?) ?? 'custom',
        title: (j['title'] as String?) ?? '',
        detail: (j['detail'] as String?) ?? '',
        points: _int(j['points'], 0),
        submitStatus: (j['submit_status'] as String?) ?? 'not_started',
      );

  final int id;
  final String subject;
  final String taskType;
  final String title;
  final String detail;
  final int points;
  final String submitStatus;
}
