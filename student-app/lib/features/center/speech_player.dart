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
  Future<void> playBytes(Uint8List bytes, String mimeType);

  Future<void> stop();

  Future<void> dispose();
}

/// 是否应走后端音频字节播放（排除 fake TTS 的 JSON 兜底）
@visibleForTesting
bool isBackendAudioResponse(String contentType, List<int> bytes) {
  final ct = contentType.split(';').first.trim().toLowerCase();
  if (!ct.startsWith('audio/')) return false;
  if (bytes.isEmpty) return false;
  // 少数网关误标 Content-Type 时，拒绝把 JSON 当音频
  if (bytes.isNotEmpty && bytes.first == 0x7B /* { */) return false;
  return true;
}

/// 设备朗读语言候选（安卓部分机型只认 zh_CN / zh）
@visibleForTesting
List<String> deviceTtsLanguageCandidates(String text) {
  final primary = speechLanguage(text);
  if (primary == 'zh-CN') return const ['zh-CN', 'zh_CN', 'zh', 'cmn-Hans-CN'];
  return const ['en-US', 'en_US', 'en'];
}

class _AudioPlayerOutput implements AudioOutput {
  _AudioPlayerOutput() : _player = AudioPlayer();

  final AudioPlayer _player;
  bool _contextReady = false;

  Future<void> _ensureContext() async {
    if (_contextReady || kIsWeb) return;
    // 听写短音频：按「语音」用途申请焦点，避免安卓静音/错误路由到通知音轨
    await _player.setAudioContext(
      AudioContext(
        android: const AudioContextAndroid(
          isSpeakerphoneOn: true,
          stayAwake: false,
          contentType: AndroidContentType.speech,
          usageType: AndroidUsageType.assistanceAccessibility,
          audioFocus: AndroidAudioFocus.gainTransientMayDuck,
        ),
        iOS: AudioContextIOS(
          category: AVAudioSessionCategory.playback,
          options: const {AVAudioSessionOptions.duckOthers},
        ),
      ),
    );
    _contextReady = true;
  }

  @override
  Future<void> playBytes(Uint8List bytes, String mimeType) async {
    await _ensureContext();
    await _player.stop();
    await _player.play(BytesSource(bytes, mimeType: mimeType));
  }

  @override
  Future<void> stop() => _player.stop();

  @override
  Future<void> dispose() => _player.dispose();
}

/// 优先播放后端 TTS 音频；后端为 fake、出错或网络失败时用设备朗读（对应旧版 speechSynthesis）
class BackendSpeechPlayer implements SpeechPlayer {
  BackendSpeechPlayer(this._api, {AudioOutput Function()? audioFactory, FlutterTts Function()? ttsFactory})
      : _audioFactory = audioFactory ?? _AudioPlayerOutput.new,
        _ttsFactory = ttsFactory ?? FlutterTts.new;

  final ApiClient _api;
  final AudioOutput Function() _audioFactory;
  final FlutterTts Function() _ttsFactory;

  // 延迟创建：仅读取 provider 时不触发平台通道
  late final AudioOutput _audio = _audioFactory();
  late final FlutterTts _tts = _ttsFactory();
  bool _audioCreated = false;
  bool _ttsCreated = false;
  bool _ttsPrepared = false;
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

  Future<void> _prepareDeviceTts(FlutterTts tts, String text) async {
    if (defaultTargetPlatform == TargetPlatform.android) {
      try {
        final engines = await tts.getEngines;
        if (engines is List && engines.isNotEmpty) {
          final names = engines.map((e) => '$e').toList();
          final preferred = names.firstWhere(
            (e) => e.toLowerCase().contains('google'),
            orElse: () => names.first,
          );
          await tts.setEngine(preferred);
        }
      } catch (_) {
        // 无引擎列表时继续用系统默认
      }
    }
    await tts.setVolume(1.0);
    await tts.setPitch(1.0);
    // 旧版浏览器语速 0.9；flutter_tts 在安卓上约 0.5 为正常语速
    await tts.setSpeechRate(kIsWeb ? 0.9 : 0.5);

    var languageSet = false;
    for (final lang in deviceTtsLanguageCandidates(text)) {
      try {
        final ok = await tts.setLanguage(lang);
        if (ok == 1 || ok == true) {
          languageSet = true;
          if (defaultTargetPlatform == TargetPlatform.android) {
            try {
              final installed = await tts.isLanguageInstalled(lang);
              if (installed == true) break;
            } catch (_) {
              break;
            }
          } else {
            break;
          }
        }
      } catch (_) {
        // 试下一个候选
      }
    }
    if (!languageSet) {
      // 仍尝试默认语言，但后续 speak 失败会抛错给 UI
      await tts.setLanguage(speechLanguage(text));
    }
    _ttsPrepared = true;
  }

  Future<bool> _hasInstalledVoice(FlutterTts tts, String text) async {
    if (defaultTargetPlatform != TargetPlatform.android) return true;
    for (final lang in deviceTtsLanguageCandidates(text)) {
      try {
        if (await tts.isLanguageInstalled(lang) == true) return true;
      } catch (_) {}
    }
    // 英文多数机型预装；isLanguageInstalled 不可用时仍允许尝试
    return speechLanguage(text) != 'zh-CN';
  }

  Future<void> _speakDevice(String text, int seq) async {
    final tts = _ttsEngine;
    if (!_ttsPrepared) {
      await _prepareDeviceTts(tts, text);
    } else {
      // 语言可能在中英听写间切换
      for (final lang in deviceTtsLanguageCandidates(text)) {
        try {
          final ok = await tts.setLanguage(lang);
          if (ok == 1 || ok == true) break;
        } catch (_) {}
      }
    }
    if (seq != _seq || _disposed) return;
    // 安卓常见：英文 TTS 有、中文语音包未装 → speak 成功但完全无声
    if (!await _hasInstalledVoice(tts, text)) {
      throw StateError('zh_tts_not_installed');
    }
    if (seq != _seq || _disposed) return;
    final result = await tts.speak(text, focus: !kIsWeb);
    if (seq != _seq || _disposed) return;
    if (result != 1 && result != true) {
      throw StateError('device_tts_failed');
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

    var usedBackendAudio = false;
    try {
      final r = await _api.getBytes('/api/tts/synthesize', query: {'text': text});
      if (seq != _seq) return;
      if (isBackendAudioResponse(r.contentType, r.bytes)) {
        final audio = _audioPlayer;
        final mime = r.contentType.split(';').first.trim();
        await audio.playBytes(Uint8List.fromList(r.bytes), mime);
        if (seq != _seq || _disposed) return;
        usedBackendAudio = true;
        return;
      }
    } catch (_) {
      if (seq != _seq) return;
      // 落到设备朗读
    }

    try {
      await _speakDevice(text, seq);
    } catch (_) {
      if (seq != _seq || _disposed) return;
      // 后端音频若已成功启动则不再抛；否则让 UI 显示「播放失败」
      if (!usedBackendAudio) rethrow;
    }
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
