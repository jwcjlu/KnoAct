import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/dictation/data/dictation_repository.dart';

void main() {
  test('DictWord.fromJson parses speak_text and accept', () {
    final w = DictWord.fromJson({
      'id': 3,
      'word': '安静',
      'extra': 'ānjìng 没有声音',
      'speak_text': '请听：安静',
      'accept': ['安静', '安靜'],
    });
    expect(w.speakText, '请听：安静');
    expect(w.accept, ['安静', '安靜']);
  });

  test('DictWord.speakText falls back to word when speak_text missing or empty', () {
    expect(DictWord(id: 1, word: '好', extra: '').speakText, '好');
    expect(DictWord.fromJson({'id': 1, 'word': '好', 'speak_text': ''}).speakText, '好');
    expect(DictWord.fromJson({'id': 1, 'word': '好', 'speak_text': '  '}).speakText, '好');
  });

  test('parseDictContent preserves speak_text in task content', () {
    final words = parseDictContent('[{"id":1,"word":"溪","speak_text":"溪水","accept":["溪"]}]');
    expect(words.length, 1);
    expect(words.first.speakText, '溪水');
    expect(words.first.accept, ['溪']);
  });
}