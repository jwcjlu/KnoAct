import 'dart:convert';

class PhonicsStage {
  const PhonicsStage({
    required this.id,
    required this.name,
    required this.pathOrderMin,
    required this.pathOrderMax,
  });

  final int id;
  final String name;
  final int pathOrderMin;
  final int pathOrderMax;

  factory PhonicsStage.fromJson(Map<String, dynamic> j) => PhonicsStage(
        id: j['id'] as int,
        name: j['name'] as String,
        pathOrderMin: j['path_order_min'] as int,
        pathOrderMax: j['path_order_max'] as int,
      );
}

class PhonicsExampleWord {
  const PhonicsExampleWord({
    required this.word,
    required this.grades,
    required this.audio,
  });

  final String word;
  final List<int> grades;
  final String audio;

  factory PhonicsExampleWord.fromJson(Map<String, dynamic> j) =>
      PhonicsExampleWord(
        word: j['word'] as String,
        grades: (j['grades'] as List<dynamic>? ?? const [])
            .map((e) => e as int)
            .toList(),
        audio: j['audio'] as String? ?? '',
      );
}

class PhonicsRule {
  const PhonicsRule({
    required this.id,
    required this.category,
    required this.grapheme,
    required this.ipa,
    required this.approxZh,
    required this.pathOrder,
    required this.notes,
    required this.ruleAudio,
    required this.exampleWords,
  });

  final String id;
  final String category;
  final String grapheme;
  final String ipa;
  final String approxZh;
  final int? pathOrder;
  final String notes;
  final String ruleAudio;
  final List<PhonicsExampleWord> exampleWords;

  factory PhonicsRule.fromJson(Map<String, dynamic> j) => PhonicsRule(
        id: j['id'] as String,
        category: j['category'] as String,
        grapheme: j['grapheme'] as String,
        ipa: j['ipa'] as String? ?? '',
        approxZh: j['approx_zh'] as String? ?? '',
        pathOrder: j['path_order'] as int?,
        notes: j['notes'] as String? ?? '',
        ruleAudio: j['rule_audio'] as String? ?? '',
        exampleWords: (j['example_words'] as List<dynamic>? ?? const [])
            .map((e) => PhonicsExampleWord.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class PhonicsCatalog {
  const PhonicsCatalog({
    required this.version,
    required this.stages,
    required this.rules,
  });

  final int version;
  final List<PhonicsStage> stages;
  final List<PhonicsRule> rules;

  factory PhonicsCatalog.parse(String jsonStr) {
    final map = jsonDecode(jsonStr) as Map<String, dynamic>;
    return PhonicsCatalog(
      version: map['version'] as int? ?? 1,
      stages: (map['stages'] as List<dynamic>? ?? const [])
          .map((e) => PhonicsStage.fromJson(e as Map<String, dynamic>))
          .toList(),
      rules: (map['rules'] as List<dynamic>? ?? const [])
          .map((e) => PhonicsRule.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  List<PhonicsRule> rulesInStage(PhonicsStage stage) {
    final list = rules.where((r) {
      final o = r.pathOrder;
      if (o == null) return false;
      return o >= stage.pathOrderMin && o <= stage.pathOrderMax;
    }).toList();
    list.sort((a, b) => (a.pathOrder ?? 0).compareTo(b.pathOrder ?? 0));
    return list;
  }

  PhonicsRule? findRule(String id) {
    for (final r in rules) {
      if (r.id == id) return r;
    }
    return null;
  }
}
