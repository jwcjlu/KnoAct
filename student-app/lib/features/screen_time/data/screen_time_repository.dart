import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'usage_api.dart';
import 'screen_time_sync.dart';

final usageApiProvider = Provider<UsageApi>((ref) => UsageApi());
final screenTimeSyncProvider = Provider<ScreenTimeSync>(
    (ref) => ScreenTimeSync(ref.watch(usageApiProvider)));
