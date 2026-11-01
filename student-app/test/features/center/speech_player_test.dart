import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/center/speech_player.dart';

class FakeApi implements ApiClient {
  @override
  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) async =>
      (bytes: const [1, 2, 3], contentType: 'audio/mpeg; charset=binary');

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeAudio implements AudioOutput {
  final calls = <String>[];

  /// 非空时 setSource 等待它完成后才返回
  Completer<void>? sourceGate;

  @override
  Future<void> setSource(Uint8List bytes, String mimeType) async {
    calls.add('setSource:$mimeType');
    final gate = sourceGate;
    if (gate != null) await gate.future;
  }

  @override
  Future<void> resume() async => calls.add('resume');

  @override
  Future<void> stop() async => calls.add('stop');

  @override
  Future<void> dispose() async => calls.add('dispose');
}

void main() {
  test('后端返回音频时设置音源后播放', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(FakeApi(), audioFactory: () => audio);
    await player.speak('hello');
    expect(audio.calls, ['setSource:audio/mpeg', 'resume']);
  });

  test('准备音源期间停止：不再开始播放', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(FakeApi(), audioFactory: () => audio);
    final gate = audio.sourceGate = Completer<void>();
    final speaking = player.speak('hello');
    await pumpEventQueue();
    expect(audio.calls, ['setSource:audio/mpeg']);
    await player.stop();
    gate.complete();
    await speaking;
    expect(audio.calls, isNot(contains('resume')));
  });

  test('准备音源期间释放：不再开始播放', () async {
    final audio = FakeAudio();
    final player = BackendSpeechPlayer(FakeApi(), audioFactory: () => audio);
    final gate = audio.sourceGate = Completer<void>();
    final speaking = player.speak('hello');
    await pumpEventQueue();
    await player.dispose();
    gate.complete();
    await speaking;
    expect(audio.calls, isNot(contains('resume')));
  });
}
