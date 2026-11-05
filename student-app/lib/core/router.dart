import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/session.dart';
import '../features/auth/ui/bind_parent_page.dart';
import '../features/auth/ui/login_page.dart';
import '../features/auth/ui/register_page.dart';
import '../features/assignment/ui/assignment_page.dart';
import '../features/center/ui/center_page.dart';
import '../features/dictation/ui/dictation_page.dart';
import '../features/home/ui/home_page.dart';
import '../features/knowledge_review/ui/knowledge_page.dart';
import '../features/math_exercise/ui/math_page.dart';
import '../features/profile/ui/profile_page.dart';
import '../features/reader/ui/reader_home_page.dart';
import '../features/reader/ui/reader_view_page.dart';
import '../features/shell/app_shell.dart';
import '../features/wrongbook/ui/wrongbook_page.dart';

/// 未登录可访问的页面
const _publicPaths = {'/login', '/register'};

/// 登录且已绑定家长后可访问的页面；登录/注册/绑定页与未知路径一律回到首页
const _shellPaths = {'/home', '/center', '/wrongbook', '/profile'};

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);
  return GoRouter(
    initialLocation: '/home',
    refreshListenable: refresh,
    redirect: (context, state) {
      final child = ref.read(sessionProvider).value;
      final path = state.uri.path;
      if (child == null) return _publicPaths.contains(path) ? null : '/login';
      // 未绑定家长：只能停留在绑定页（parent_bound 来自登录响应 / 缓存 / 最近一次 /me）
      if (!child.parentBound) return path == '/bind-parent' ? null : '/bind-parent';
      if (_shellPaths.contains(path) ||
          path == '/assignment' ||
          path == '/math' ||
          path == '/knowledge' ||
          path == '/dictation' ||
          path == '/reader' ||
          path == '/reader/view') {
        return null;
      }
      return '/home';
    },
    routes: [
      GoRoute(path: '/login', builder: (_, _) => const LoginPage()),
      GoRoute(path: '/register', builder: (_, _) => const RegisterPage()),
      GoRoute(path: '/bind-parent', builder: (_, _) => const BindParentPage()),
      GoRoute(path: '/assignment', builder: (_, _) => const AssignmentPage()),
      GoRoute(path: '/math', builder: (_, _) => const MathPage()),
      GoRoute(path: '/knowledge', builder: (_, _) => const KnowledgePage()),
      GoRoute(path: '/dictation', builder: (_, _) => const DictationPage()),
      GoRoute(path: '/reader', builder: (_, _) => const ReaderHomePage()),
      GoRoute(path: '/reader/view', builder: (_, _) => const ReaderViewPage()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => AppShell(navigationShell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, _) => const HomePage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/center', builder: (_, _) => const CenterPage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/wrongbook', builder: (_, _) => const WrongbookPage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, _) => const ProfilePage())]),
        ],
      ),
    ],
  );
});
