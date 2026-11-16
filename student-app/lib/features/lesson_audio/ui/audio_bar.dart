import 'dart:async';

import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import '../models/lesson_audio.dart';

/// 单个教材音频的播放条：可拖拽进度，整段播，或按 marks 分段（点某段从 start_sec 起播）。
class AudioBar extends StatefulWidget {
  const AudioBar({super.key, required this.audio, required this.url});
  final LessonAudio audio;
  final String url;

  @override
  State<AudioBar> createState() => _AudioBarState();
}

class _AudioBarState extends State<AudioBar> {
  final _player = AudioPlayer();
  final List<StreamSubscription<dynamic>> _subs = [];
  bool _playing = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  @override
  void initState() {
    super.initState();
    _subs.add(_player.onPositionChanged.listen((d) {
      if (mounted) setState(() => _position = d);
    }));
    _subs.add(_player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _duration = d);
    }));
    _subs.add(_player.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playing = false);
    }));
  }

  @override
  void dispose() {
    for (final s in _subs) {
      s.cancel();
    }
    _player.dispose();
    super.dispose();
  }

  Future<void> _play({double fromSec = 0}) async {
    await _player.play(UrlSource(widget.url),
        position: Duration(milliseconds: (fromSec * 1000).round()));
    if (mounted) setState(() => _playing = true);
  }

  Future<void> _stop() async {
    await _player.stop();
    if (mounted) {
      setState(() {
        _playing = false;
        _position = Duration.zero;
      });
    }
  }

  Future<void> _seek(double sec) async {
    await _player.seek(Duration(milliseconds: (sec * 1000).round()));
    if (mounted) setState(() => _position = Duration(milliseconds: (sec * 1000).round()));
  }

  @override
  Widget build(BuildContext context) {
    final marks = widget.audio.marks;
    final totalMs = _duration.inMilliseconds;
    final posMs = _position.inMilliseconds.clamp(0, totalMs > 0 ? totalMs : 0);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(children: [
          const Icon(Icons.volume_up, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(widget.audio.unitLabel, maxLines: 1, overflow: TextOverflow.ellipsis)),
          IconButton(
            icon: Icon(_playing ? Icons.stop : Icons.play_arrow),
            onPressed: () => _playing ? _stop() : _play(),
          ),
        ]),
        if (totalMs > 0)
          Slider(
            value: posMs.toDouble(),
            max: totalMs.toDouble(),
            onChanged: _seek,
          ),
        if (marks.isNotEmpty)
          Wrap(spacing: 8, children: [
            for (final m in marks)
              ActionChip(label: Text(m.label), onPressed: () => _play(fromSec: m.startSec)),
          ]),
      ],
    );
  }
}
