import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import '../ui/im_chat_modes.dart';

class AskAiConfig {
  const AskAiConfig({this.provider = 'deepseek', this.defaultModel = 'deepseek-chat'});

  final String provider;
  final String defaultModel;

  List<String> get modelOptions => chatModelOptionsForProvider(provider, configuredModel: defaultModel);
}

final askAiConfigProvider = FutureProvider<AskAiConfig>((ref) async {
  try {
    final raw = await ref.read(apiClientProvider).get('/api/config');
    final m = asMap(raw);
    final provider = '${m['ai_provider'] ?? 'deepseek'}';
    final model = '${m['ai_model'] ?? 'deepseek-chat'}';
    return AskAiConfig(provider: provider, defaultModel: model);
  } catch (_) {
    return const AskAiConfig();
  }
});
