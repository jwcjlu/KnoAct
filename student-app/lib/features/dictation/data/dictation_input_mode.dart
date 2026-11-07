enum DictationInputMode {
  paperPhoto('paper_photo'),
  onScreen('on_screen');

  const DictationInputMode(this.apiValue);

  final String apiValue;

  static DictationInputMode fromApi(String raw) {
    for (final m in DictationInputMode.values) {
      if (m.apiValue == raw) return m;
    }
    return DictationInputMode.paperPhoto;
  }

  String get label => switch (this) {
        DictationInputMode.paperPhoto => '纸上听写（家长设置）',
        DictationInputMode.onScreen => '屏上手写（家长设置）',
      };
}
