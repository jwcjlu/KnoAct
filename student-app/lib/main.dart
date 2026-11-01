import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  // 关闭 Riverpod 3 的自动重试：加载失败由页面的「重试」按钮处理
  runApp(ProviderScope(retry: (_, _) => null, child: const StudentApp()));
}
