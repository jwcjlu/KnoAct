import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/math_exercise/data/math_models.dart';
import 'package:student_app/features/math_exercise/data/math_repository.dart';
import 'package:student_app/features/math_exercise/math_controller.dart';

class FakeMathRepository implements MathRepository {
  FakeMathRepository(this.material);

  MathTaskMaterial material;

  @override
  Future<MathTaskMaterial> fetchMaterial(int taskId) async => material;

  @override
  Future<MathGradeResult> gradeCalc({required int userId, required int taskId, required List<String> answers}) async =>
      const MathGradeResult(correct: 1, total: 1, results: [true]);

  @override
  Future<MathWordItem> uploadWordPhoto(int taskId, int wordIndex, List<int> bytes, {String filename = 'math_word.jpg'}) async =>
      const MathWordItem(index: 0, question: '', photoPath: 'p.jpg', aiStatus: 'ok', parentStatus: 'none');
}

void main() {
  test('MathController grades calc then allows submit when words ready', () async {
    final repo = FakeMathRepository(MathTaskMaterial(
      calc: const [MathCalcItem(index: 0, question: '1+1')],
      word: const [MathWordItem(index: 0, question: '应用题', photoPath: 'x', aiStatus: 'ok', parentStatus: 'none')],
    ));
    final container = ProviderContainer(overrides: [
      mathRepositoryProvider.overrideWithValue(repo),
      currentChildIdProvider.overrideWith((ref) => 4),
    ]);
    addTearDown(container.dispose);

    final ctl = container.read(mathControllerProvider.notifier);
    await ctl.init(taskId: 9, title: '数学');
    var s = container.read(mathControllerProvider);
    expect(s.canSubmit, isFalse);

    ctl.setCalcAnswer(0, '2');
    await ctl.gradeCalc();
    s = container.read(mathControllerProvider);
    expect(s.calcGraded, isTrue);
    expect(s.canSubmit, isTrue);
  });
}
