import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/ask/data/read_ask_cards_models.dart';
import 'package:student_app/features/ask/immersive_quiz_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  ProviderContainer make() {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(immersiveQuizProvider.notifier)
        .state = const ImmersiveQuizState(
      quizId: 1,
      questions: [
        ReaderQuizQuestion(id: 'q1', prompt: 'p', choices: ['a', 'b']),
      ],
    );
    return container;
  }

  test('选了答案再指句子，两样都记住', () {
    final container = make();
    final ctl = container.read(immersiveQuizProvider.notifier);
    ctl.pickAnswer('q1', 0);
    ctl.pickEvidence('q1', '第一句。');
    final s = container.read(immersiveQuizProvider);
    expect(s.answers['q1'], 0);
    expect(s.evidencePicks['q1'], '第一句。');
  });

  test('改选项清掉旧出处（避免张冠李戴）', () {
    final container = make();
    final ctl = container.read(immersiveQuizProvider.notifier);
    ctl.pickAnswer('q1', 0);
    ctl.pickEvidence('q1', '第一句。');
    ctl.pickAnswer('q1', 1);
    final s = container.read(immersiveQuizProvider);
    expect(s.answers['q1'], 1);
    expect(s.evidencePicks.containsKey('q1'), isFalse);
  });

  test('重复点同一选项不清掉已指的句子', () {
    final container = make();
    final ctl = container.read(immersiveQuizProvider.notifier);
    ctl.pickAnswer('q1', 0);
    ctl.pickEvidence('q1', '第一句。');
    ctl.pickAnswer('q1', 0);
    final s = container.read(immersiveQuizProvider);
    expect(s.evidencePicks['q1'], '第一句。');
  });
}
