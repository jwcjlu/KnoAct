import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/phonics/data/phonics_catalog.dart';
import 'package:student_app/features/phonics/data/phonics_repository.dart';
import 'package:student_app/features/phonics/ui/phonics_page.dart';

class _FakeRepo extends PhonicsRepository {
  _FakeRepo(this.catalog);
  final PhonicsCatalog catalog;

  @override
  Future<PhonicsCatalog> loadCatalog() async => catalog;
}

void main() {
  final catalog = PhonicsCatalog.parse('''
{
  "version": 1,
  "stages": [
    {"id": 1, "name": "高频单辅音", "path_order_min": 1, "path_order_max": 20},
    {"id": 2, "name": "其余辅音", "path_order_min": 21, "path_order_max": 35}
  ],
  "rules": [
    {
      "id": "vowel.a.short",
      "category": "vowel",
      "grapheme": "a",
      "ipa": "/æ/",
      "approx_zh": "短 a",
      "path_order": 5,
      "notes": "note-a",
      "rule_audio": "phonics/audio/rule/vowel.a.short.wav",
      "example_words": [
        {"word": "cat", "grades": [3, 5], "audio": "phonics/audio/word/cat.wav"}
      ]
    },
    {
      "id": "consonant.b.primary",
      "category": "consonant",
      "grapheme": "b",
      "ipa": "/b/",
      "approx_zh": "b",
      "path_order": 25,
      "notes": "",
      "rule_audio": "phonics/audio/rule/consonant.b.primary.wav",
      "example_words": []
    }
  ]
}
''');

  testWidgets('shows stages and rules for selected stage', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          phonicsRepositoryProvider.overrideWithValue(_FakeRepo(catalog)),
        ],
        child: const MaterialApp(home: PhonicsPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('自然拼读'), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-stage-tabs')), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-stage-1')), findsOneWidget);
    expect(find.text('高频单辅音'), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-rule-vowel.a.short')), findsOneWidget);
    expect(find.text('a'), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-rule-consonant.b.primary')), findsNothing);

    await tester.tap(find.byKey(const ValueKey('phonics-stage-2')));
    await tester.pumpAndSettle();
    expect(find.text('其余辅音'), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-rule-consonant.b.primary')), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-rule-vowel.a.short')), findsNothing);
  });

  testWidgets('opens rule detail with play control and examples', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          phonicsRepositoryProvider.overrideWithValue(_FakeRepo(catalog)),
        ],
        child: const MaterialApp(home: PhonicsPage()),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('phonics-rule-vowel.a.short')));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('phonics-play-rule')), findsOneWidget);
    expect(find.byKey(const ValueKey('phonics-word-cat')), findsOneWidget);
    expect(find.textContaining('不判定对错'), findsOneWidget);
  });
}
