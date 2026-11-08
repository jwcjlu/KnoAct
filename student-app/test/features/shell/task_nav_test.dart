import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/shell/task_nav.dart';

void main() {
  test('parseReturnTo 缺省为 /home', () {
    expect(parseReturnTo(null), '/home');
    expect(parseReturnTo(''), '/home');
  });

  test('parseReturnTo 白名单', () {
    expect(parseReturnTo('/home'), '/home');
    expect(parseReturnTo('/center'), '/center');
    expect(parseReturnTo('/evil'), '/home');
  });

  test('taskRoute 携带 returnTo', () {
    expect(taskRoute('/reader', returnTo: '/center'), '/reader?returnTo=%2Fcenter');
    expect(
      taskRoute('/dictation', returnTo: '/home', query: {'taskId': '3'}),
      '/dictation?returnTo=%2Fhome&taskId=3',
    );
  });
}
