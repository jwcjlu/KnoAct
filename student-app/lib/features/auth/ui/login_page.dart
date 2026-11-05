import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../session.dart';
import 'auth_errors.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _loginName = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();
  bool _otpMode = false;
  bool _busy = false;
  bool _otpSent = false;
  String? _error;

  @override
  void dispose() {
    _loginName.dispose();
    _password.dispose();
    _code.dispose();
    super.dispose();
  }

  bool get _canSubmit {
    if (_busy || _loginName.text.trim().isEmpty) return false;
    return _otpMode ? _code.text.trim().isNotEmpty : _password.text.isNotEmpty;
  }

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

  Future<void> _submit() => _run(() {
        final s = ref.read(sessionProvider.notifier);
        return _otpMode ? s.otpLogin(_loginName.text, _code.text) : s.login(_loginName.text, _password.text);
      });

  Future<void> _sendOtp() => _run(() async {
        await ref.read(sessionProvider.notifier).sendOtp(_loginName.text);
        if (mounted) setState(() => _otpSent = true);
      });

  void _switchMode() => setState(() {
        _otpMode = !_otpMode;
        _error = null;
      });

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
                const Text('你的 AI 学习伙伴', textAlign: TextAlign.center, style: TextStyle(color: AppColors.gray)),
                const SizedBox(height: 28),
                TextField(
                  key: const Key('loginName'),
                  controller: _loginName,
                  decoration: const InputDecoration(labelText: '登录名', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 12),
                if (_otpMode) ...[
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(
                      child: TextField(
                        key: const Key('otpCode'),
                        controller: _code,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: '短信验证码', border: OutlineInputBorder()),
                        onChanged: (_) => setState(() => _error = null),
                        onSubmitted: (_) => canSubmit ? _submit() : null,
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      height: 56,
                      child: OutlinedButton(
                        onPressed: _busy || _loginName.text.trim().isEmpty ? null : _sendOtp,
                        child: Text(_otpSent ? '重新发送' : '发送验证码'),
                      ),
                    ),
                  ]),
                  if (_otpSent)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text('验证码已发送到该账号绑定的手机', style: TextStyle(fontSize: 12, color: AppColors.gray)),
                    ),
                ] else
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
                TextButton(onPressed: _switchMode, child: Text(_otpMode ? '使用密码登录' : '使用验证码登录')),
                TextButton(onPressed: () => context.go('/register'), child: const Text('还没有账号？去注册')),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
