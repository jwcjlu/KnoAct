import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/screen_time/data/screen_time_sync.dart';
import 'package:student_app/features/screen_time/data/screen_time_notifier.dart';
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

  test('groupTotalsFromDay：按组精确归集，未知包不计入', () {
    final day = {
      'com.douyin': 3000,   // 娱乐类
      'com.game': 1000,     // 娱乐类
      'com.knoact': 5000,   // 学习类
      'com.unknown': 9999,  // 未映射 → 不计入任何组
    };
    final pkgGroups = {
      'com.douyin': 1,
      'com.game': 1,
      'com.knoact': 2,
    };
    final totals = groupTotalsFromDay(day, pkgGroups);
    expect(totals[1], 4000); // 娱乐类 = 3000 + 1000
    expect(totals[2], 5000); // 学习类
    expect(totals.containsKey(3), isFalse); // 未知组不出现
    // 未知包 com.unknown 未计入任何组
    expect(totals.values.fold<int>(0, (a, b) => a + b), 9000);
  });

  test('reminder 状态机：超时只提醒一次', () async {
    SharedPreferences.setMockInitialValues({});
    final n = ReminderState();
    // 第一次超时 → 应提醒
    expect(n.shouldNotify(overtime: true, warned: false), isTrue);
    await n.markNotified('2026-11-04', '娱乐类');
    // 已提醒过 → 不再提醒
    expect(n.shouldNotify(overtime: true, warned: true), isFalse);
    // 回到未超时 → 不提醒
    expect(n.shouldNotify(overtime: false, warned: true), isFalse);
  });

  testWidgets('权限页显示引导文案', (tester) async {
    await tester.pumpWidget(
        ProviderScope(child: MaterialApp(home: UsagePermissionPage())));
    expect(find.textContaining('使用情况访问'), findsWidgets);
  });
}
