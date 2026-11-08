import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../shell/task_page_app_bar.dart';
import '../data/dictation_input_mode.dart';
import '../dictation_controller.dart';
import '../dictation_input_mode_provider.dart';
import 'dictation_on_screen_view.dart';
import 'dictation_paper_flow.dart';

class DictationPage extends ConsumerWidget {
  const DictationPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final modeAsync = ref.watch(dictationInputModeProvider);
    final base = ref.watch(dictationControllerProvider);

    return modeAsync.when(
      loading: () => Scaffold(
        appBar: TaskPageAppBar(title: base.title.isEmpty ? '生词听写' : base.title),
        body: const Center(child: CircularProgressIndicator()),
      ),
      // 偏好拉取失败时与后端默认一致：纸上听写（勿回落屏写）
      error: (_, __) => DictationPaperFlow(
        base: base,
        modeLabel: DictationInputMode.paperPhoto.label,
      ),
      data: (mode) {
        if (mode == DictationInputMode.onScreen) {
          return const DictationOnScreenView();
        }
        return DictationPaperFlow(base: base, modeLabel: mode.label);
      },
    );
  }
}
