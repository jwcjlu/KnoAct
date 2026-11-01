import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import 'center_logic.dart';

abstract class SpeechPlayer {
  Future<void> speak(String text);
}

/// 优先播放后端 TTS 音频；后端为 fake、出错或网络失败时用设备朗读（对应旧版 speechSynthesis）
class BackendSpeechPlayer implements SpeechPlayer {
  BackendSpeechPlayer(this._api);

  final ApiClient _api;
  final AudioPlayer _audio = AudioPlayer();
  final FlutterTts _tts = FlutterTts();

  @override
  Future<void> speak(String raw) async {
    final text = raw.replaceAll('\n', ' ');
    try {
      final r = await _api.getBytes('/api/tts/synthesize', query: {'text': text});
      if (r.contentType.startsWith('audio/')) {
        await _audio.play(BytesSource(Uint8List.fromList(r.bytes), mimeType: 'audio/mpeg'));
        return;
      }
    } catch (_) {
      // 落到设备朗读
    }
    await _tts.setLanguage(speechLanguage(text));
    // 旧版浏览器语速 0.9；flutter_tts 在安卓上 0.5 为正常语速
    await _tts.setSpeechRate(kIsWeb ? 0.9 : 0.45);
    await _tts.speak(text);
  }
}

final speechPlayerProvider = Provider<SpeechPlayer>((ref) => BackendSpeechPlayer(ref.watch(apiClientProvider)));
