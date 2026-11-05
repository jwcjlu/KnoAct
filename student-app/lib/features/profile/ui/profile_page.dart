import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../auth/session.dart';
import '../../auth/ui/auth_errors.dart';
import '../../home/home_controller.dart';

const _genders = {'unknown': '不填', 'male': '男孩', 'female': '女孩'};
final _birthMonthRe = RegExp(r'^\d{4}-(0[1-9]|1[0-2])$');

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  late final TextEditingController _name;
  late final TextEditingController _birth;
  late final TextEditingController _interests;
  late String _gender;
  bool _busy = false;
  String? _error;
  String? _saved;

  @override
  void initState() {
    super.initState();
    final c = ref.read(sessionProvider).value;
    _name = TextEditingController(text: c?.name ?? '');
    _birth = TextEditingController(text: c?.birthMonth ?? '');
    _interests = TextEditingController(text: c?.interests ?? '');
    _gender = _genders.containsKey(c?.gender) ? c!.gender : 'unknown';
  }

  @override
  void dispose() {
    _name.dispose();
    _birth.dispose();
    _interests.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    final birth = _birth.text.trim();
    if (name.isEmpty) {
      setState(() => _error = '昵称不能为空');
      return;
    }
    if (birth.isNotEmpty && !_birthMonthRe.hasMatch(birth)) {
      setState(() => _error = '出生年月格式应为 YYYY-MM，例如 2016-09');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _saved = null;
    });
    try {
      await ref.read(sessionProvider.notifier).updateProfile(
            displayName: name,
            birthMonth: birth.isEmpty ? null : birth,
            gender: _gender,
            interests: _interests.text.split(RegExp(r'[,，、\s]+')).where((s) => s.isNotEmpty).join(','),
          );
      if (mounted) _saved = '已保存';
    } catch (e) {
      _error = authErrorText(e, fallback: '保存失败，请检查网络或后端服务');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final child = ref.watch(sessionProvider).value;
    final points = ref.watch(pointsProvider);
    return ListView(padding: const EdgeInsets.all(20), children: [
      SectionCard(
        child: Row(children: [
          CircleAvatar(radius: 26, child: Text(child == null || child.name.isEmpty ? '' : child.name.characters.last)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(child?.name ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              Text(
                points.when(data: (p) => '$p 积分', loading: () => '积分加载中…', error: (_, _) => '积分加载失败'),
                style: const TextStyle(color: AppColors.gray),
              ),
            ]),
          ),
        ]),
      ),
      const SizedBox(height: 16),
      SectionCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('个人资料', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          Text('登录名：${child?.loginName ?? ''}', key: const Key('profileLoginName'), style: const TextStyle(color: AppColors.gray)),
          const SizedBox(height: 12),
          TextField(
            key: const Key('profileDisplayName'),
            controller: _name,
            decoration: const InputDecoration(labelText: '昵称', border: OutlineInputBorder()),
            onChanged: (_) => setState(() => _saved = null),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('profileBirthMonth'),
            controller: _birth,
            keyboardType: TextInputType.datetime,
            decoration: const InputDecoration(labelText: '出生年月（YYYY-MM）', border: OutlineInputBorder()),
            onChanged: (_) => setState(() => _saved = null),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            key: const Key('profileGender'),
            initialValue: _gender,
            decoration: const InputDecoration(labelText: '性别', border: OutlineInputBorder()),
            items: [for (final e in _genders.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
            onChanged: (v) => setState(() {
              _gender = v ?? 'unknown';
              _saved = null;
            }),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('profileInterests'),
            controller: _interests,
            decoration: const InputDecoration(labelText: '兴趣（用逗号分隔）', border: OutlineInputBorder()),
            onChanged: (_) => setState(() => _saved = null),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          if (_saved != null) ...[
            const SizedBox(height: 8),
            Text(_saved!, style: const TextStyle(color: Colors.green)),
          ],
          const SizedBox(height: 12),
          FilledButton(onPressed: _busy ? null : _save, child: const Text('保存资料')),
        ]),
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () => ref.read(sessionProvider.notifier).logout(),
        icon: const Icon(Icons.logout),
        label: const Text('退出登录'),
      ),
    ]);
  }
}
