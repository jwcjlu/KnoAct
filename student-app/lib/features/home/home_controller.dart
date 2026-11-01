import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/home_models.dart';
import 'data/home_repository.dart';
import 'home_logic.dart';

class HomeData {
  const HomeData({required this.childId, required this.subject, required this.snapshot, required this.tasks, required this.points});

  /// 数据所属的孩子；与当前登录孩子不一致时界面按加载中处理
  final int childId;
  final String subject;
  final HomeSnapshot snapshot;
  final List<StudyTask> tasks;
  final int points;
}

class HomeController extends AsyncNotifier<HomeData> {
  /// 最近一次请求的学科；界面显示的学科以 state.value?.subject 为准
  String _subject = subjects.first;
  int? _uid;

  /// 每次发起加载自增，只有最新一次的结果会写入 state
  int _gen = 0;

  @override
  Future<HomeData> build() {
    final uid = ref.watch(currentChildIdProvider);
    _gen++;
    if (uid != _uid) {
      _uid = uid;
      _subject = subjects.first;
    }
    // 未登录（退出登录到跳回登录页之间）保持加载中：不请求，也不产生错误
    if (uid == null) return Completer<HomeData>().future;
    return _load(uid, _subject);
  }

  Future<HomeData> _load(int uid, String subject) async {
    final repo = ref.read(homeRepositoryProvider);
    final results = await Future.wait([
      repo.snapshot(uid, subject),
      repo.tasks(uid, apiDate(DateTime.now())),
      repo.balance(uid),
    ]);
    return HomeData(
      childId: uid,
      subject: subject,
      snapshot: results[0] as HomeSnapshot,
      tasks: results[1] as List<StudyTask>,
      points: results[2] as int,
    );
  }

  Future<void> _refresh(String subject) async {
    final uid = ref.read(currentChildIdProvider);
    if (uid == null) return;
    final gen = ++_gen;
    final next = await AsyncValue.guard(() => _load(uid, subject));
    if (!ref.mounted || gen != _gen) return;
    state = next;
  }

  Future<void> setSubject(String subject) async {
    if (ref.read(currentChildIdProvider) == null) return;
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
    if (uid == null) throw StateError('未登录');
    final ok = await ref.read(homeRepositoryProvider).redeem(uid, device, minutes);
    if (!ok) return '积分还不够，再完成几个任务吧';
    final msg = '已兑换${device == 'tablet' ? '平板' : '手机'} $minutes 分钟，等待家长确认';
    if (!ref.mounted || ref.read(currentChildIdProvider) != uid) return msg;
    await reload();
    if (ref.mounted) ref.invalidate(pointsProvider);
    return msg;
  }
}

final homeControllerProvider = AsyncNotifierProvider.autoDispose<HomeController, HomeData>(HomeController.new);

/// 「我的」页积分（以 /api/points/balance 为准）；未登录时保持加载中
final pointsProvider = FutureProvider.autoDispose<int>((ref) {
  final uid = ref.watch(currentChildIdProvider);
  if (uid == null) return Completer<int>().future;
  return ref.read(homeRepositoryProvider).balance(uid);
});
