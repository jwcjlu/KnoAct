import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import 'center_logic.dart';

abstract class SpeechPlayer {
  Future<void> speak(String text);

  /// 停止当前播放，并丢弃尚未开始播放的请求；不抛异常
  Future<void> stop();

  Future<void> dispose();
}

/// 音频字节播放的最小接口，测试中可替换
abstract class AudioOutput {
  Future<void> setSource(Uint8List bytes, String mimeType);

  Future<void> resume();

  Future<void> stop();

  Future<void> dispose();
}

class _AudioPlayerOutput implements AudioOutput {
  final _player = AudioPlayer();

  @override
  Future<void> setSource(Uint8List bytes, String mimeType) => _player.setSource(BytesSource(bytes, mimeType: mimeType));

  @override
  Future<void> resume() => _player.resume();

  @override
  Future<void> stop() => _player.stop();

  @override
  Future<void> dispose() => _player.dispose();
}

/// 优先播放后端 TTS 音频；后端为 fake、出错或网络失败时用设备朗读（对应旧版 speechSynthesis）
class BackendSpeechPlayer implements SpeechPlayer {
  BackendSpeechPlayer(this._api, {AudioOutput Function()? audioFactory}) : _audioFactory = audioFactory ?? _AudioPlayerOutput.new;

  final ApiClient _api;
  final AudioOutput Function() _audioFactory;

  // 延迟创建：仅读取 provider 时不触发平台通道
  late final AudioOutput _audio = _audioFactory();
  late final FlutterTts _tts = FlutterTts();
  bool _audioCreated = false;
  bool _ttsCreated = false;
  int _seq = 0;
  bool _disposed = false;

  AudioOutput get _audioPlayer {
    _audioCreated = true;
    return _audio;
  }

  FlutterTts get _ttsEngine {
    _ttsCreated = true;
    return _tts;
  }

  Future<void> _stopAll() async {
    try {
      if (_audioCreated) await _audio.stop();
    } finally {
      if (_ttsCreated) await _tts.stop();
    }
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
        final audio = _audioPlayer;
        // 准备音源可能较慢；期间 stop()/dispose() 过则不再开始播放
        await audio.setSource(Uint8List.fromList(r.bytes), r.contentType.split(';').first.trim());
        if (seq != _seq || _disposed) return;
        await audio.resume();
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
  Future<void> stop() async {
    if (_disposed) return;
    _seq++;
    try {
      await _stopAll();
    } catch (_) {
      // 停止失败不影响后续播放
    }
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
