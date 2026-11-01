import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/home_models.dart';
import 'data/home_repository.dart';
import 'home_logic.dart';

class HomeData {
  const HomeData({required this.subject, required this.snapshot, required this.tasks, required this.points});

  final String subject;
  final HomeSnapshot snapshot;
  final List<StudyTask> tasks;
  final int points;
}

class HomeController extends AsyncNotifier<HomeData> {
  String _subject = subjects.first;

  @override
  Future<HomeData> build() {
    ref.watch(sessionProvider);
    return _load();
  }

  Future<HomeData> _load() async {
    final uid = ref.read(currentChildIdProvider);
    final repo = ref.read(homeRepositoryProvider);
    final results = await Future.wait([
      repo.snapshot(uid, _subject),
      repo.tasks(uid, apiDate(DateTime.now())),
      repo.balance(uid),
    ]);
    return HomeData(
      subject: _subject,
      snapshot: results[0] as HomeSnapshot,
      tasks: results[1] as List<StudyTask>,
      points: results[2] as int,
    );
  }

  Future<void> setSubject(String subject) async {
    if (subject == _subject) return;
    _subject = subject;
    state = await AsyncValue.guard(_load);
  }

  Future<void> reload() async {
    state = await AsyncValue.guard(_load);
  }

  /// 返回提示文案
  Future<String> redeem(String device, int minutes) async {
    final uid = ref.read(currentChildIdProvider);
    final ok = await ref.read(homeRepositoryProvider).redeem(uid, device, minutes);
    if (!ok) return '积分还不够，再完成几个任务吧';
    await reload();
    ref.invalidate(pointsProvider);
    return '已兑换${device == 'tablet' ? '平板' : '手机'} $minutes 分钟，等待家长确认';
  }
}

final homeControllerProvider = AsyncNotifierProvider<HomeController, HomeData>(HomeController.new);

/// 「我的」页积分（以 /api/points/balance 为准）
final pointsProvider = FutureProvider<int>((ref) {
  ref.watch(sessionProvider);
  return ref.read(homeRepositoryProvider).balance(ref.read(currentChildIdProvider));
});
