import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../wrongbook/data/bucket_models.dart';
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
    // 学年桶切换（含首次解析出 active 桶）时重新加载，把 bucketId 带进 balance 查询
    ref.watch(homeBucketsProvider.select((s) => s.bucketId));
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
      repo.balance(uid, bucketId: ref.read(homeBucketsProvider).bucketId),
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

/// 首页积分学年桶选择（active + archived）。
/// 换孩子时重建并解析出默认选中的 active 桶。
class HomeBucketsState {
  const HomeBucketsState({this.buckets = const [], this.bucketId, this.isReadOnly = false});

  final List<BucketInfo> buckets;
  final int? bucketId;
  final bool isReadOnly;
}

class HomeBucketsController extends Notifier<HomeBucketsState> {
  int _loadToken = 0;

  int? get _uid => ref.read(currentChildIdProvider);

  @override
  HomeBucketsState build() {
    ref.watch(currentChildIdProvider);
    _loadToken++;
    _resolve();
    return const HomeBucketsState();
  }

  bool _stale(int token, int uid) => !ref.mounted || token != _loadToken || _uid != uid;

  Future<void> setBucket(int id) async {
    if (state.bucketId == id) return;
    final bucket = _bucket(id);
    state = HomeBucketsState(
      buckets: state.buckets,
      bucketId: id,
      isReadOnly: bucket == null ? false : !bucket.isActive,
    );
    ref.invalidate(pointsProvider);
  }

  BucketInfo? _bucket(int id) {
    for (final b in state.buckets) {
      if (b.id == id) return b;
    }
    return null;
  }

  Future<void> _resolve() async {
    final uid = _uid;
    if (uid == null) return;
    final token = ++_loadToken;
    final buckets = await AsyncValue.guard(() => ref.read(homeRepositoryProvider).buckets(uid));
    if (_stale(token, uid)) return;
    final list = buckets.value ?? const <BucketInfo>[];
    final active = list.where((b) => b.isActive);
    final selected = active.isNotEmpty ? active.first : (list.isNotEmpty ? list.first : null);
    state = HomeBucketsState(
      buckets: list,
      bucketId: selected?.id,
      isReadOnly: selected == null ? false : !selected.isActive,
    );
  }
}

final homeBucketsProvider = NotifierProvider<HomeBucketsController, HomeBucketsState>(HomeBucketsController.new);

/// 「我的」页积分（以 /api/points/balance 为准）；未登录时保持加载中
final pointsProvider = FutureProvider.autoDispose<int>((ref) {
  final uid = ref.watch(currentChildIdProvider);
  if (uid == null) return Completer<int>().future;
  final bucketId = ref.watch(homeBucketsProvider).bucketId;
  return ref.read(homeRepositoryProvider).balance(uid, bucketId: bucketId);
});
