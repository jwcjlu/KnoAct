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
  /// 最近一次请求的学科；界面显示的学科以 state.value?.subject 为准
  String _subject = subjects.first;

  /// 每次发起加载自增，只有最新一次的结果会写入 state
  int _gen = 0;

  @override
  Future<HomeData> build() {
    ref.watch(sessionProvider);
    _gen++;
    return _load(_subject);
  }

  Future<HomeData> _load(String subject) async {
    final uid = ref.read(currentChildIdProvider);
    final repo = ref.read(homeRepositoryProvider);
    final results = await Future.wait([
      repo.snapshot(uid, subject),
      repo.tasks(uid, apiDate(DateTime.now())),
      repo.balance(uid),
    ]);
    return HomeData(
      subject: subject,
      snapshot: results[0] as HomeSnapshot,
      tasks: results[1] as List<StudyTask>,
      points: results[2] as int,
    );
  }

  Future<void> _refresh(String subject) async {
    final gen = ++_gen;
    final next = await AsyncValue.guard(() => _load(subject));
    if (!ref.mounted || gen != _gen) return;
    state = next;
  }

  Future<void> setSubject(String subject) async {
    if (subject == _subject && subject == state.value?.subject) return;
    final previous = state.value?.subject ?? _subject;
    _subject = subject;
    await _refresh(subject);
    if (ref.mounted && _subject == subject && state.hasError) _subject = previous;
  }

  Future<void> reload() => _refresh(_subject);

  /// 返回提示文案
  Future<String> redeem(String device, int minutes) async {
    final uid = ref.read(currentChildIdProvider);
    final ok = await ref.read(homeRepositoryProvider).redeem(uid, device, minutes);
    if (!ok) return '积分还不够，再完成几个任务吧';
    final msg = '已兑换${device == 'tablet' ? '平板' : '手机'} $minutes 分钟，等待家长确认';
    if (!ref.mounted) return msg;
    await reload();
    if (ref.mounted) ref.invalidate(pointsProvider);
    return msg;
  }
}

final homeControllerProvider = AsyncNotifierProvider<HomeController, HomeData>(HomeController.new);

/// 「我的」页积分（以 /api/points/balance 为准）
final pointsProvider = FutureProvider<int>((ref) {
  ref.watch(sessionProvider);
  return ref.read(homeRepositoryProvider).balance(ref.read(currentChildIdProvider));
});
