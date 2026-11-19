import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/center/speech_player.dart';

class FakeApi implements ApiClient {
  FakeApi({this.contentType = 'audio/mpeg; charset=binary', this.bytes = const [1, 2, 3]});

  final String contentType;
  final List<int> bytes;

  @override
  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) async =>
      (bytes: bytes, contentType: contentType);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeAudio implements AudioOutput {
  final calls = <String>[];

  /// 非空时 playBytes 等待它完成后才返回
  Completer<void>? playGate;

  @override
  Future<void> playBytes(Uint8List bytes, String mimeType) async {
    calls.add('playBytes:$mimeType');
    final gate = playGate;
    if (gate != null) await gate.future;
  }

  @override
  Future<void> stop() async => calls.add('stop');

  @override
  Future<void> dispose() async => calls.add('dispose');
}

void main() {
  test('isBackendAudioResponse 识别真实音频、拒绝 JSON', () {
    expect(isBackendAudioResponse('audio/mpeg', [0xFF, 0xFB]), isTrue);
    expect(isBackendAudioResponse('application/json', '{'.codeUnits), isFalse);
    expect(isBackendAudioResponse('audio/mpeg', '{'.codeUnits), isFalse);
    expect(isBackendAudioResponse('audio/mpeg', []), isFalse);
  });

  test('deviceTtsLanguageCandidates 中文含安卓变体', () {
    expect(deviceTtsLanguageCandidates('箩'), containsAll(['zh-CN', 'zh_CN', 'zh']));
    expect(deviceTtsLanguageCandidates('hello'), contains('en-US'));
  });

  test('后端返回音频时直接播放字节', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(FakeApi(), audioFactory: () => audio);
    await player.speak('hello');
    expect(audio.calls, ['playBytes:audio/mpeg']);
  });

  test('后端 fake JSON 不走音频播放', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(
      FakeApi(contentType: 'application/json', bytes: '{"provider":"fake"}'.codeUnits),
      audioFactory: () => audio,
    );
    // 设备 TTS 在测试环境可能失败，但不应调用 playBytes
    try {
      await player.speak('箩');
    } catch (_) {}
    expect(audio.calls, isEmpty);
  });

  test('准备音源期间停止：不再开始播放', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(FakeApi(), audioFactory: () => audio);
    final gate = audio.playGate = Completer<void>();
    final speaking = player.speak('hello');
    await pumpEventQueue();
    expect(audio.calls, ['playBytes:audio/mpeg']);
    await player.stop();
    gate.complete();
    await speaking;
    // stop 之后 seq 已变；playBytes 返回后不应再有额外播放调用
    expect(audio.calls.where((c) => c.startsWith('playBytes')), hasLength(1));
  });

  test('准备音源期间释放：不再开始播放', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(FakeApi(), audioFactory: () => audio);
    final gate = audio.playGate = Completer<void>();
    final speaking = player.speak('hello');
    await pumpEventQueue();
    await player.dispose();
    gate.complete();
    await speaking;
    expect(audio.calls.where((c) => c.startsWith('playBytes')), hasLength(1));
  });
}
