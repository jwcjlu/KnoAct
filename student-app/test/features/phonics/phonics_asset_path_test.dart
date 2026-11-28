import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/phonics/data/phonics_asset_path.dart';

void main() {
  test('assetSourcePath strips leading assets/ and keeps phonics prefix', () {
    expect(
      phonicsAssetSourcePath('phonics/audio/rule/vowel.a.short.wav'),
      'phonics/audio/rule/vowel.a.short.wav',
    );
    expect(
      phonicsAssetSourcePath('assets/phonics/audio/word/cat.wav'),
      'phonics/audio/word/cat.wav',
    );
  });

  test('empty path stays empty', () {
    expect(phonicsAssetSourcePath(''), '');
  });
}
