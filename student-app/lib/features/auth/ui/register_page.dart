import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../session.dart';
import 'auth_errors.dart';

/// 孩子注册：登录名 + 密码（两次确认）。成功后自动登录，router 会引导去绑定家长。
class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key});

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final _loginName = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _loginName.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  bool get _mismatch => _confirm.text.isNotEmpty && _confirm.text != _password.text;

  bool get _canSubmit =>
      !_busy && _loginName.text.trim().isNotEmpty && _password.text.isNotEmpty && _confirm.text == _password.text;

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(sessionProvider.notifier).register(_loginName.text, _password.text);
    } catch (e) {
      _error = authErrorText(e, fallback: '注册失败，请检查网络或后端服务');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('注册账号'),
        leading: BackButton(onPressed: () => context.go('/login')),
      ),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                TextField(
                  key: const Key('registerLoginName'),
                  controller: _loginName,
                  decoration: const InputDecoration(labelText: '登录名', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('registerPassword'),
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: '密码', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('registerConfirm'),
                  controller: _confirm,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: '确认密码',
                    border: const OutlineInputBorder(),
                    errorText: _mismatch ? '两次输入的密码不一致' : null,
                  ),
                  onChanged: (_) => setState(() => _error = null),
                  onSubmitted: (_) => _submit(),
                ),
                const SizedBox(height: 8),
                const Text('注册后需要绑定家长账号才能开始学习', style: TextStyle(fontSize: 12, color: AppColors.gray)),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 20),
                FilledButton(onPressed: _canSubmit ? _submit : null, child: const Text('注册')),
                TextButton(onPressed: () => context.go('/login'), child: const Text('已有账号？去登录')),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
