import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../home/home_controller.dart';

const _allowedReturnTo = {'/home', '/center'};

/// 解析任务页 ``returnTo`` 查询参数；非法或缺省为 ``/home``。
String parseReturnTo(String? raw) {
  if (raw == null || raw.isEmpty) return '/home';
  return _allowedReturnTo.contains(raw) ? raw : '/home';
}

/// 构建带 ``returnTo`` 的任务路由（可附加其它 query）。
String taskRoute(String path, {required String returnTo, Map<String, String>? query}) {
  return Uri(
    path: path,
    queryParameters: {
      'returnTo': parseReturnTo(returnTo),
      ...?query,
    },
  ).toString();
}

/// 当前路由上的 ``returnTo``，无则 ``/home``。
String returnToFromState(BuildContext context) =>
    parseReturnTo(GoRouterState.of(context).uri.queryParameters['returnTo']);

void popOrReturn(BuildContext context, {String? returnTo}) {
  if (context.canPop()) {
    context.pop();
    return;
  }
  context.go(parseReturnTo(returnTo));
}

void goHome(WidgetRef ref, BuildContext context) {
  context.go('/home');
  ref.read(homeControllerProvider.notifier).reload();
}
