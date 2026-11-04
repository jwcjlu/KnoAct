import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'features/screen_time/data/screen_time_worker.dart';

void main() {
  if (!kIsWeb) registerScreenTimeWorker();
  // 关闭 Riverpod 3 的自动重试：加载失败由页面的「重试」按钮处理
  runApp(ProviderScope(retry: (_, _) => null, child: const StudentApp()));
}
