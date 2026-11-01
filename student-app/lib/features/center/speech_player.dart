import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import 'center_logic.dart';

abstract class SpeechPlayer {
  Future<void> speak(String text);

  Future<void> dispose();
}

/// 优先播放后端 TTS 音频；后端为 fake、出错或网络失败时用设备朗读（对应旧版 speechSynthesis）
class BackendSpeechPlayer implements SpeechPlayer {
  BackendSpeechPlayer(this._api);

  final ApiClient _api;

  // 延迟创建：仅读取 provider 时不触发平台通道
  late final AudioPlayer _audio = AudioPlayer();
  late final FlutterTts _tts = FlutterTts();
  bool _audioCreated = false;
  bool _ttsCreated = false;
  int _seq = 0;
  bool _disposed = false;

  AudioPlayer get _audioPlayer {
    _audioCreated = true;
    return _audio;
  }

  FlutterTts get _ttsEngine {
    _ttsCreated = true;
    return _tts;
  }

  Future<void> _stopAll() async {
    if (_audioCreated) await _audio.stop();
    if (_ttsCreated) await _tts.stop();
  }

  @override
  Future<void> speak(String raw) async {
    final text = raw.replaceAll('\n', ' ');
    if (_disposed || text.trim().isEmpty) return;
    final seq = ++_seq;
    try {
      await _stopAll();
    } catch (_) {
      // 停止失败不影响本次播放
    }
    try {
      final r = await _api.getBytes('/api/tts/synthesize', query: {'text': text});
      if (seq != _seq) return;
      if (r.contentType.startsWith('audio/')) {
        await _audioPlayer.play(BytesSource(Uint8List.fromList(r.bytes), mimeType: r.contentType.split(';').first.trim()));
        return;
      }
    } catch (_) {
      if (seq != _seq) return;
      // 落到设备朗读
    }
    final tts = _ttsEngine;
    await tts.setLanguage(speechLanguage(text));
    // 旧版浏览器语速 0.9；flutter_tts 在安卓上 0.5 为正常语速
    await tts.setSpeechRate(kIsWeb ? 0.9 : 0.45);
    if (seq != _seq) return;
    await tts.speak(text);
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _seq++;
    try {
      if (_audioCreated) {
        try {
          await _audio.stop();
        } finally {
          await _audio.dispose();
        }
      }
    } finally {
      if (_ttsCreated) await _tts.stop();
    }
  }
}

final speechPlayerProvider = Provider<SpeechPlayer>((ref) {
  final p = BackendSpeechPlayer(ref.watch(apiClientProvider));
  ref.onDispose(p.dispose);
  return p;
});
