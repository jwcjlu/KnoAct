import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/auth/session.dart';
import 'api_client.dart';
import 'config.dart';

/// 令牌与 401 处理都用 `ref.read` 惰性读取，避免与 [sessionProvider] 形成初始化环
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient(
      resolveApiBase(),
      accessToken: () => ref.read(sessionStoreProvider).readAccessToken(),
      onUnauthorized: () => ref.read(sessionProvider.notifier).expire(),
    ));
