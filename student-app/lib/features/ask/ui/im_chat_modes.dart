import 'package:flutter/material.dart';

/// 沉浸阅读对话模式（对齐 Web `CHAT_MODES`）
class ImChatModeDef {
  const ImChatModeDef({required this.id, required this.name, required this.desc, required this.icon});

  final String id;
  final String name;
  final String desc;
  final IconData icon;
}

const imChatModes = <ImChatModeDef>[
  ImChatModeDef(id: 'chat', name: '对话', desc: '普通问答', icon: Icons.auto_awesome_outlined),
  ImChatModeDef(id: 'quiz', name: '测验', desc: '3 道理解题', icon: Icons.format_list_bulleted),
  ImChatModeDef(id: 'questions', name: '主动提问', desc: 'AI 考考你', icon: Icons.auto_awesome_outlined),
  ImChatModeDef(id: 'visualize', name: '可视化', desc: '思维导图 / 流程图', icon: Icons.grid_view_outlined),
  ImChatModeDef(id: 'solve', name: '解题', desc: '分步骤讲解', icon: Icons.edit_outlined),
  ImChatModeDef(id: 'more', name: '更多', desc: '更多能力', icon: Icons.menu),
];

ImChatModeDef? imChatModeById(String id) {
  for (final m in imChatModes) {
    if (m.id == id) return m;
  }
  return null;
}

/// 走后端 `/api/ask/stream` 的模式
bool imModeUsesAskStream(String id) => id == 'chat' || id == 'visualize' || id == 'solve';

String shortModelName(String model) => model.length > 18 ? '${model.substring(0, 18)}…' : model;

/// Web `aiProviders` 内置模型列表（与 `frontend/app.js` 一致）
const _builtinModels = <String, List<String>>{
  'deepseek': ['deepseek-chat', 'deepseek-reasoner'],
  'glm': ['glm-4-plus', 'glm-4-flash'],
  'openai': ['gpt-4o', 'gpt-4o-mini', 'deepseek-chat', 'claude-sonnet-4-5'],
};

List<String> chatModelOptionsForProvider(String provider, {String? configuredModel}) {
  final base = _builtinModels[provider] ?? _builtinModels['deepseek']!;
  final set = <String>{...base};
  if (configuredModel != null && configuredModel.isNotEmpty) set.add(configuredModel);
  return set.toList();
}
