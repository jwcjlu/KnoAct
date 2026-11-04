import 'package:flutter/material.dart';

import 'data/home_models.dart';

const subjects = ['语文', '英语', '数学'];

bool isDone(StudyTask t) => t.submitStatus == 'approved';

({int done, int total, int percent}) dayProgress(List<StudyTask> tasks) {
  final done = tasks.where(isDone).length;
  final total = tasks.length;
  return (done: done, total: total, percent: total == 0 ? 0 : (done * 100 / total).round());
}

Map<String, ({int done, int total})> subjectProgress(List<StudyTask> tasks) => {
      for (final s in subjects)
        s: (
          done: tasks.where((t) => t.subject == s && isDone(t)).length,
          total: tasks.where((t) => t.subject == s).length,
        ),
    };

/// 与旧版一致：无学科的任务出现在每个学科下
({List<StudyTask> todo, List<StudyTask> done}) groupForSubject(List<StudyTask> tasks, String subject) {
  final list = tasks.where((t) => t.subject.isEmpty || t.subject == subject).toList();
  return (todo: list.where((t) => !isDone(t)).toList(), done: list.where(isDone).toList());
}

enum TaskAction { done, waiting, openReading, openListening, openMath, openKnowledge, openDictation, comingSoon }

TaskAction taskAction(StudyTask t) {
  if (t.submitStatus == 'approved') return TaskAction.done;
  if (t.submitStatus == 'submitted') return TaskAction.waiting;
  if (t.taskType == 'reading') return TaskAction.openReading;
  if (t.taskType == 'listening') return TaskAction.openListening;
  if (t.taskType == 'math') return TaskAction.openMath;
  if (t.taskType == 'knowledge') return TaskAction.openKnowledge;
  if (t.taskType == 'dictation') return TaskAction.openDictation;
  return TaskAction.comingSoon;
}

class TaskMeta {
  const TaskMeta(this.tag, this.minutes, this.icon, this.color);

  final String tag;
  final String minutes;
  final IconData icon;
  final Color color;
}

const _blue = Color(0xFF3158E8);
const _green = Color(0xFF2E8B5A);
const _orange = Color(0xFFDC872D);

const _metas = {
  'dictation': TaskMeta('当前进度', '约 8 分钟', Icons.edit, _blue),
  'knowledge': TaskMeta('重点巩固', '约 10 分钟', Icons.psychology, _green),
  'review': TaskMeta('遗忘曲线', '约 10 分钟', Icons.psychology, _green),
  'reading': TaskMeta('阅读理解', '约 12 分钟', Icons.menu_book, _orange),
  'listening': TaskMeta('听力理解', '约 8 分钟', Icons.headphones, _blue),
  'math': TaskMeta('数学练习', '约 10 分钟', Icons.edit, _orange),
  'custom': TaskMeta('自定义', '', Icons.auto_awesome, _orange),
};

TaskMeta taskMeta(String taskType) => _metas[taskType] ?? _metas['custom']!;

String greeting(int hour) => hour < 6
    ? '夜深了'
    : hour < 12
        ? '早上好'
        : hour < 18
            ? '下午好'
            : '晚上好';

const _week = ['一', '二', '三', '四', '五', '六', '日'];

String dateLabel(DateTime d) => '${d.month} 月 ${d.day} 日，星期${_week[d.weekday - 1]}';

String apiDate(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class Poem {
  const Poem(this.name, this.title, this.text, this.author);

  final String name;
  final String title;
  final String text;
  final String author;
}

/// 与旧版 POEMS 相同，竹/兰/梅/菊按天轮换
const poems = [
  Poem('竹', '竹石', '咬定青山不放松，立根原在破岩中。\n千磨万击还坚劲，任尔东西南北风。', '清 · 郑板桥'),
  Poem('兰', '幽兰', '幽兰在山谷，本自无人识。\n只为馨香重，求者遍山隅。', '陈毅'),
  Poem('梅', '梅花', '墙角数枝梅，凌寒独自开。\n遥知不是雪，为有暗香来。', '宋 · 王安石'),
  Poem('菊', '菊花', '不是花中偏爱菊，此花开尽更无花。', '唐 · 元稹'),
];

Poem todayPoem(DateTime now) => poems[(now.millisecondsSinceEpoch ~/ 86400000) % poems.length];
