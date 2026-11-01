import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/session.dart';
import '../features/auth/ui/login_page.dart';
import '../features/center/ui/center_page.dart';
import '../features/home/ui/home_page.dart';
import '../features/profile/ui/profile_page.dart';
import '../features/shell/app_shell.dart';

/// 登录后可访问的页面；登录页与未知路径一律回到首页
const _shellPaths = {'/home', '/center', '/profile'};

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);
  return GoRouter(
    initialLocation: '/home',
    refreshListenable: refresh,
    redirect: (context, state) {
      final loggedIn = ref.read(sessionProvider).value != null;
      final path = state.uri.path;
      if (!loggedIn) return path == '/login' ? null : '/login';
      return _shellPaths.contains(path) ? null : '/home';
    },
    routes: [
      GoRoute(path: '/login', builder: (_, _) => const LoginPage()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => AppShell(navigationShell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, _) => const HomePage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/center', builder: (_, _) => const CenterPage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, _) => const ProfilePage())]),
        ],
      ),
    ],
  );
});
