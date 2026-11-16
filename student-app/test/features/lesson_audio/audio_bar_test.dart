import 'dart:async';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:audioplayers_platform_interface/audioplayers_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/lesson_audio/models/lesson_audio.dart';
import 'package:student_app/features/lesson_audio/ui/audio_bar.dart';

/// 记录 seek 调用、可主动 emit duration/seekComplete 事件的假平台。
class _FakeAudioPlatform extends AudioplayersPlatformInterface {
  final _events = StreamController<AudioEvent>.broadcast();
  final seeks = <Duration>[];

  @override
  Stream<AudioEvent> getEventStream(String playerId) => _events.stream;

  @override
  Future<void> create(String playerId) async {}

  @override
  Future<void> dispose(String playerId) async {}

  @override
  Future<void> stop(String playerId) async {}

  @override
  Future<void> seek(String playerId, Duration position) async {
    seeks.add(position);
    _events.add(const AudioEvent(eventType: AudioEventType.seekComplete));
  }

  @override
  Future<void> resume(String playerId) async {}

  @override
  Future<void> pause(String playerId) async {}

  @override
  Future<void> release(String playerId) async {}

  @override
  Future<void> setSourceUrl(String playerId, String url,
      {bool? isLocal, String? mimeType}) async {}

  @override
  Future<void> setBalance(String playerId, double balance) async {}

  @override
  Future<void> setVolume(String playerId, double volume) async {}

  @override
  Future<void> setReleaseMode(String playerId, ReleaseMode releaseMode) async {}

  @override
  Future<void> setPlaybackRate(String playerId, double playbackRate) async {}

  @override
  Future<void> setPlayerMode(String playerId, PlayerMode playerMode) async {}

  @override
  Future<void> setAudioContext(String playerId, AudioContext audioContext) async {}

  @override
  Future<void> setSourceBytes(String playerId, Uint8List bytes,
      {String? mimeType}) async {}

  @override
  Future<int?> getDuration(String playerId) async => 60000;

  @override
  Future<int?> getCurrentPosition(String playerId) async => 0;

  @override
  Future<void> emitLog(String playerId, String message) async {}

  @override
  Future<void> emitError(String playerId, String code, String message) async {}
}

class _FakeGlobalPlatform extends GlobalAudioplayersPlatformInterface {
  final _events = StreamController<GlobalAudioEvent>.broadcast();

  @override
  Stream<GlobalAudioEvent> getGlobalEventStream() => _events.stream;

  @override
  Future<void> init() async {}

  @override
  Future<void> setGlobalAudioContext(AudioContext ctx) async {}

  @override
  Future<void> emitGlobalLog(String message) async {}

  @override
  Future<void> emitGlobalError(String code, String message) async {}
}

Widget _wrap(AudioBar bar) => MaterialApp(home: Scaffold(body: bar));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _FakeAudioPlatform platform;
  late _FakeGlobalPlatform globalPlatform;

  setUp(() {
    platform = _FakeAudioPlatform();
    AudioplayersPlatformInterface.instance = platform;
    globalPlatform = _FakeGlobalPlatform();
    GlobalAudioplayersPlatformInterface.instance = globalPlatform;
  });

  tearDown(() async {
    await platform._events.close();
    await globalPlatform._events.close();
  });

  LessonAudio audio({String label = 'Unit 1', List<AudioMark> marks = const []}) =>
      LessonAudio(
        id: 1,
        lessonId: 54,
        unitLabel: label,
        audioPath: 'a',
        marks: marks,
      );

  testWidgets('无时长时（未收到 duration 事件）不显示 Slider', (tester) async {
    await tester.pumpWidget(_wrap(AudioBar(audio: audio(), url: 'http://x/a.mp3')));
    expect(find.byType(Slider), findsNothing);
  });

  testWidgets('收到 duration 事件后显示 Slider', (tester) async {
    await tester.pumpWidget(_wrap(AudioBar(audio: audio(), url: 'http://x/a.mp3')));
    platform._events.add(const AudioEvent(
      eventType: AudioEventType.duration,
      duration: Duration(seconds: 60),
    ));
    await tester.pump();
    expect(find.byType(Slider), findsOneWidget);
  });

  testWidgets('拖拽 Slider 调 seek 到对应位置', (tester) async {
    await tester.pumpWidget(_wrap(AudioBar(audio: audio(), url: 'http://x/a.mp3')));
    platform._events.add(const AudioEvent(
      eventType: AudioEventType.duration,
      duration: Duration(seconds: 60),
    ));
    await tester.pump();

    final slider = tester.widget<Slider>(find.byType(Slider));
    // 拖到中点（30s）。
    slider.onChanged!(30000);
    await tester.pump();

    expect(platform.seeks, isNotEmpty);
    expect(platform.seeks.last, const Duration(seconds: 30));
  });
}
