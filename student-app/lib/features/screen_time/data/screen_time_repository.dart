import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/config.dart';
import 'usage_api.dart';
import 'screen_time_sync.dart';

final usageApiProvider = Provider<UsageApi>((ref) => UsageApi());

final screenTimeSyncDioProvider = Provider<Dio>(
    (ref) => Dio(BaseOptions(baseUrl: resolveApiBase())));

final screenTimeSyncProvider = Provider<ScreenTimeSync>((ref) => ScreenTimeSync(
    ref.watch(usageApiProvider), ref.watch(screenTimeSyncDioProvider)));
