import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
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
        appBar: AppBar(title: Text(base.title.isEmpty ? '生词听写' : base.title), backgroundColor: AppColors.bg),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (_, __) => const DictationOnScreenView(),
      data: (mode) {
        if (mode == DictationInputMode.onScreen) {
          return const DictationOnScreenView();
        }
        return DictationPaperFlow(base: base, modeLabel: mode.label);
      },
    );
  }
}
