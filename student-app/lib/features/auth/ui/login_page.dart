import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../session.dart';
import 'auth_errors.dart';

/// 登录页：固定展示 **登录名 + 密码**（不再在同一页切换成「仅验证码」，避免看不到密码框）。
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _loginName = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _loginName.dispose();
    _password.dispose();
    super.dispose();
  }

  bool get _canSubmit => !_busy && _loginName.text.trim().isNotEmpty && _password.text.isNotEmpty;

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } catch (e) {
      _error = authErrorText(e, fallback: '登录失败，请检查网络或后端服务');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() =>
      _run(() => ref.read(sessionProvider.notifier).login(_loginName.text, _password.text));

  @override
  Widget build(BuildContext context) {
    final canSubmit = _canSubmit;
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Icon(Icons.auto_awesome, size: 48, color: AppColors.blue),
                const SizedBox(height: 12),
                const Text('知学伴', textAlign: TextAlign.center, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
                const Text('账号登录', textAlign: TextAlign.center, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                const Text('你的 AI 学习伙伴', textAlign: TextAlign.center, style: TextStyle(color: AppColors.gray)),
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: Text(
                    '请填写登录名和密码。老账号登录名多为原姓名，初始密码 ChangeMe123；新同学请先注册。',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: AppColors.gray, height: 1.4),
                  ),
                ),
                const SizedBox(height: 20),
                TextField(
                  key: const Key('loginName'),
                  controller: _loginName,
                  decoration: const InputDecoration(labelText: '登录名', border: OutlineInputBorder()),
                  textInputAction: TextInputAction.next,
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('password'),
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: '密码', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                  onSubmitted: (_) => canSubmit ? _submit() : null,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 20),
                FilledButton(onPressed: canSubmit ? _submit : null, child: const Text('登录')),
                const SizedBox(height: 8),
                TextButton(onPressed: () => context.go('/login-otp'), child: const Text('已绑手机？用验证码登录')),
                TextButton(onPressed: () => context.go('/register'), child: const Text('还没有账号？去注册')),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
