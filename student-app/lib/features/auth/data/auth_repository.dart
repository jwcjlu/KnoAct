import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

class Child {
  const Child(this.id, this.name);

  final int id;
  final String name;

  @override
  bool operator ==(Object other) => other is Child && other.id == id && other.name == name;

  @override
  int get hashCode => Object.hash(id, name);
}

class NotAChildException implements Exception {}

class AuthRepository {
  AuthRepository(this._api);

  final ApiClient _api;

  /// 按名字登录；后端找不到名字会自动创建孩子账号。返回非孩子账号时抛 [NotAChildException]。
  Future<Child> login(String name) async {
    final d = asMap(await _api.post('/api/auth/login', body: {'name': name}));
    if (d['role'] != 'child') throw NotAChildException();
    return Child((d['id'] as num).toInt(), d['name'] as String);
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) => AuthRepository(ref.watch(apiClientProvider)));
