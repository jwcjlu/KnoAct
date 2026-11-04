import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/screen_time/data/screen_time_sync.dart';
import 'package:student_app/features/screen_time/ui/usage_permission_page.dart';

void main() {
  test('overtime 判定：超过上限', () {
    expect(isOvertime(5000, 3600), isTrue);
  });

  test('overtime 判定：未超上限', () {
    expect(isOvertime(100, 3600), isFalse);
  });

  test('overtime 判定：无上限 = 永不超时', () {
    expect(isOvertime(99999, null), isFalse);
  });

  test('warn 阈值：达 80% 预警', () {
    expect(hitWarnThreshold(3000, 3600), isTrue); // 83%
    expect(hitWarnThreshold(100, 3600), isFalse);
  });

  testWidgets('权限页显示引导文案', (tester) async {
    await tester.pumpWidget(
        ProviderScope(child: MaterialApp(home: UsagePermissionPage())));
    expect(find.textContaining('使用情况访问'), findsWidgets);
  });
}
