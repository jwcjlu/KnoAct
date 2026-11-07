import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:student_app/features/dictation/data/dictation_repository.dart';
import 'package:student_app/features/dictation/paper_dictation_controller.dart';

void main() {
  test('advanceListen moves to upload after last word', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final ctl = container.read(paperDictationControllerProvider.notifier);
    ctl.bootstrap(
      taskId: 1,
      title: 't',
      subject: '语文',
      words: const [
        DictWord(id: 1, word: 'a', extra: 'a1'),
        DictWord(id: 2, word: 'b', extra: 'b1'),
      ],
    );
    ctl.advanceListen();
    expect(container.read(paperDictationControllerProvider).idx, 1);
    ctl.advanceListen();
    expect(container.read(paperDictationControllerProvider).phase, PaperDictationPhase.upload);
  });

  test('firstRoundWrong kept on first grading round', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final ctl = container.read(paperDictationControllerProvider.notifier);
    ctl.bootstrap(
      taskId: null,
      title: '',
      subject: '语文',
      words: const [DictWord(id: 1, word: '好', extra: 'hǎo 好的')],
    );
    ctl.applyGradeResultsForTest([
      const DictGradeItem(index: 0, isCorrect: false, written: '女子'),
    ]);
    final s = container.read(paperDictationControllerProvider);
    expect(s.firstRoundWrong.length, 1);
    expect(s.firstRoundWrong.first.word, '好');
    expect(s.wrong.length, 1);
  });
}
