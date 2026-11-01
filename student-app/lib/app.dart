import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router.dart';
import 'core/theme.dart';
import 'features/auth/session.dart';

class StudentApp extends ConsumerWidget {
  const StudentApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 会话（本地存储）读取完成前不建路由，避免先跳登录页再跳首页
    final session = ref.watch(sessionProvider);
    if (!session.hasValue && !session.hasError) {
      return MaterialApp(
        theme: buildTheme(),
        home: const Scaffold(body: Center(child: CircularProgressIndicator())),
      );
    }
    return MaterialApp.router(
      title: '知学伴 · 学生端',
      theme: buildTheme(),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
