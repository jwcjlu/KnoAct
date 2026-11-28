import 'package:audioplayers/audioplayers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'data/phonics_asset_path.dart';

class PhonicsAudioPlayer {
  PhonicsAudioPlayer({AudioPlayer? player}) : _player = player ?? AudioPlayer();

  final AudioPlayer _player;
  String? _current;

  String? get currentPath => _current;

  Future<void> playAsset(String catalogPath) async {
    final src = phonicsAssetSourcePath(catalogPath);
    if (src.isEmpty) return;
    await _player.stop();
    _current = src;
    await _player.play(AssetSource(src));
  }

  Future<void> stop() async {
    _current = null;
    await _player.stop();
  }

  Future<void> dispose() async {
    await _player.dispose();
  }
}

final phonicsAudioPlayerProvider = Provider<PhonicsAudioPlayer>((ref) {
  final p = PhonicsAudioPlayer();
  ref.onDispose(p.dispose);
  return p;
});
