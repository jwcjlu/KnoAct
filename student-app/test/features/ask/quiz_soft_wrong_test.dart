import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/ask/ui/immersive_quiz_cards.dart';

void main() {
  test('expression_weak 时选错的项降为中性色，不显示红叉', () {
    final v = choiceVisualFor(
      index: 1,
      chosen: 1,
      submitted: true,
      correctIndex: 0,
      selectedIndex: 1,
      isCorrect: false,
      verdict: 'expression_weak',
      nChoices: 4,
    );
    expect(v, ChoiceVisual.softWrong);
    expect(v, isNot(ChoiceVisual.wrong));
  });

  test('not_understood 时选错的项仍是红叉', () {
    final v = choiceVisualFor(
      index: 1,
      chosen: 1,
      submitted: true,
      correctIndex: 0,
      selectedIndex: 1,
      isCorrect: false,
      verdict: 'not_understood',
      nChoices: 4,
    );
    expect(v, ChoiceVisual.wrong);
  });
}
