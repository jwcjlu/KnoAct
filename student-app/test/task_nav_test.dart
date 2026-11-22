import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/shell/task_nav.dart';

void main() {
  test('taskRoute 传 query 时问号不被转义（否则路由匹配不上）', () {
    final built = taskRoute('/bank-exercise', returnTo: '/home', query: {
      'bank_id': '8',
      'ids': '5694,5695',
      'task_id': '519',
      'extra_bank_ids': '9',
    });
    expect(built.contains('%3F'), isFalse,
        reason: '把 "?a=1" 整串当 path 会把 ? 转义成 %3F，点了没反应');
    expect(built.startsWith('/bank-exercise?'), isTrue);

    final uri = Uri.parse(built);
    expect(uri.path, '/bank-exercise');
    expect(uri.queryParameters['bank_id'], '8');
    expect(uri.queryParameters['ids'], '5694,5695');
    expect(uri.queryParameters['extra_bank_ids'], '9');
    expect(uri.queryParameters['returnTo'], '/home');
  });
}
