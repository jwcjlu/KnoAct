import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/home_logic.dart';

StudyTask task(int id, String subject, String type, String status) => StudyTask(
    id: id, subject: subject, taskType: type, title: 't$id', detail: '', points: 20, submitStatus: status);

void main() {
  final tasks = [
    task(1, '语文', 'dictation', 'approved'),
    task(2, '语文', 'reading', 'not_started'),
    task(3, '英语', 'listening', 'submitted'),
    task(4, '数学', 'math', 'approved'),
    task(5, '', 'custom', 'not_started'),
  ];

  test('今日总进度：approved 才算完成', () {
    final p = dayProgress(tasks);
    expect(p.done, 2);
    expect(p.total, 5);
    expect(p.percent, 40);
    expect(dayProgress([]).percent, 0);
  });

  test('各学科进度', () {
    final m = subjectProgress(tasks);
    expect(m['语文'], (done: 1, total: 2));
    expect(m['英语'], (done: 0, total: 1));
    expect(m['数学'], (done: 1, total: 1));
  });

  test('按学科分组：无学科的任务出现在每个学科', () {
    final g = groupForSubject(tasks, '语文');
    expect(g.todo.map((t) => t.id), [2, 5]);
    expect(g.done.map((t) => t.id), [1]);
  });

  test('任务按钮动作', () {
    expect(taskAction(task(1, '语文', 'dictation', 'approved')), TaskAction.done);
    expect(taskAction(task(1, '语文', 'math', 'submitted')), TaskAction.waiting);
    expect(taskAction(task(1, '语文', 'reading', 'not_started')), TaskAction.openReading);
    expect(taskAction(task(1, '英语', 'listening', 'not_started')), TaskAction.openListening);
    expect(taskAction(task(1, '语文', 'dictation', 'not_started')), TaskAction.openDictation);
    expect(taskAction(task(1, '语文', 'math', 'not_started')), TaskAction.openMath);
    expect(taskAction(task(1, '语文', 'knowledge', 'not_started')), TaskAction.openKnowledge);
    expect(taskAction(task(1, '语文', 'practice', 'not_started')), TaskAction.openBankPractice);
    for (final type in ['review', 'custom']) {
      expect(taskAction(task(1, '语文', type, 'not_started')), TaskAction.comingSoon);
    }
  });

  test('任务类型元信息与旧版一致', () {
    expect(taskMeta('dictation').tag, '当前进度');
    expect(taskMeta('reading').minutes, '约 12 分钟');
    expect(taskMeta('unknown').tag, '自定义');
  });

  test('问候语按时段', () {
    expect(greeting(3), '夜深了');
    expect(greeting(9), '早上好');
    expect(greeting(15), '下午好');
    expect(greeting(20), '晚上好');
  });

  test('日期文案与接口日期', () {
    final d = DateTime(2026, 11, 1);
    expect(dateLabel(d), '11 月 1 日，星期日');
    expect(apiDate(d), '2026-11-01');
  });

  test('古诗按天轮换', () {
    final day0 = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
    expect(todayPoem(day0).name, '竹');
    expect(todayPoem(day0.add(const Duration(days: 1))).name, '兰');
    expect(todayPoem(day0.add(const Duration(days: 4))).name, '竹');
  });
}
