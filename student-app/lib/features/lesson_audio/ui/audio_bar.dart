import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import '../models/lesson_audio.dart';

/// 单个教材音频的播放条：整段播，或按 marks 分段（点某段从 start_sec 起播）。
class AudioBar extends StatefulWidget {
  const AudioBar({super.key, required this.audio, required this.url});
  final LessonAudio audio;
  final String url;

  @override
  State<AudioBar> createState() => _AudioBarState();
}

class _AudioBarState extends State<AudioBar> {
  final _player = AudioPlayer();
  bool _playing = false;

  @override
  void dispose() { _player.dispose(); super.dispose(); }

  Future<void> _play({double fromSec = 0}) async {
    await _player.play(UrlSource(widget.url),
        position: Duration(milliseconds: (fromSec * 1000).round()));
    if (mounted) setState(() => _playing = true);
  }

  Future<void> _stop() async {
    await _player.stop();
    if (mounted) setState(() => _playing = false);
  }

  @override
  Widget build(BuildContext context) {
    final marks = widget.audio.marks;
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
        if (marks.isNotEmpty)
          Wrap(spacing: 8, children: [
            for (final m in marks)
              ActionChip(label: Text(m.label), onPressed: () => _play(fromSec: m.startSec)),
          ]),
      ],
    );
  }
}
