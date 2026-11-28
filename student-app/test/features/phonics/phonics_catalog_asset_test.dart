import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/phonics/data/phonics_catalog.dart';

void main() {
  test('bundled catalog.json matches export (66 rules, 7 stages)', () {
    final file = File('assets/phonics/catalog.json');
    expect(file.existsSync(), isTrue, reason: 'run export_flutter_catalog.py');
    final catalog = PhonicsCatalog.parse(file.readAsStringSync());
    expect(catalog.stages, hasLength(7));
    expect(catalog.rules, hasLength(66));
    // every stage has at least one rule
    for (final s in catalog.stages) {
      expect(
        catalog.rulesInStage(s),
        isNotEmpty,
        reason: 'stage ${s.id} ${s.name}',
      );
    }
    // sample audio paths exist on disk
    final a = catalog.findRule('vowel.a.short');
    expect(a, isNotNull);
    final ruleFile = File('assets/${a!.ruleAudio}');
    expect(ruleFile.existsSync(), isTrue, reason: a.ruleAudio);
    final word = a.exampleWords.first;
    expect(File('assets/${word.audio}').existsSync(), isTrue);
  });
}
