import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../session.dart';
import 'auth_errors.dart';

/// 未绑定家长时唯一可访问的页面：输入家长邀请码（立即绑定），
/// 或输入家长登录名发起申请（等待家长审批）。
class BindParentPage extends ConsumerStatefulWidget {
  const BindParentPage({super.key});

  @override
  ConsumerState<BindParentPage> createState() => _BindParentPageState();
}

class _BindParentPageState extends ConsumerState<BindParentPage> {
  final _code = TextEditingController();
  final _parent = TextEditingController();
  bool _busy = false;
  String? _error;
  String? _info;

  @override
  void dispose() {
    _code.dispose();
    _parent.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, {String? success}) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
      _info = null;
    });
    try {
      await action();
      if (mounted) _info = success;
    } catch (e) {
      _error = authErrorText(e, fallback: '绑定失败，请检查网络或后端服务');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // 绑定成功后 session 刷新 → router 自动离开本页
  Future<void> _bindCode() => _run(() => ref.read(sessionProvider.notifier).bindByCode(_code.text));

  Future<void> _requestParent() => _run(
        () => ref.read(sessionProvider.notifier).requestParent(_parent.text),
        success: '申请已发送，请让家长在家长端审批；通过后点「我已通过，刷新」',
      );

  Future<void> _refresh() => _run(() => ref.read(sessionProvider.notifier).refreshMe());

  @override
  Widget build(BuildContext context) {
    final child = ref.watch(sessionProvider).value;
    return Scaffold(
      appBar: AppBar(
        title: const Text('绑定家长'),
        actions: [
          TextButton(onPressed: () => ref.read(sessionProvider.notifier).logout(), child: const Text('退出登录')),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Text('${child?.name ?? ''}，先绑定家长账号吧',
                    textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                const Text('绑定后家长可以管理你的教材和学习任务',
                    textAlign: TextAlign.center, style: TextStyle(color: AppColors.gray)),
                const SizedBox(height: 24),
                TextField(
                  key: const Key('inviteCode'),
                  controller: _code,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(labelText: '家长邀请码', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 8),
                FilledButton(onPressed: !_busy && _code.text.trim().isNotEmpty ? _bindCode : null, child: const Text('用邀请码绑定')),
                const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Divider()),
                TextField(
                  key: const Key('parentLoginName'),
                  controller: _parent,
                  decoration: const InputDecoration(labelText: '家长登录名', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                    onPressed: !_busy && _parent.text.trim().isNotEmpty ? _requestParent : null, child: const Text('向家长发送申请')),
                if (_info != null) ...[
                  const SizedBox(height: 8),
                  Text(_info!, style: const TextStyle(color: AppColors.gray)),
                  TextButton(onPressed: _busy ? null : _refresh, child: const Text('我已通过，刷新')),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
