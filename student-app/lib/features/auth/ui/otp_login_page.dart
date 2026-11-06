import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../session.dart';
import 'auth_errors.dart';

/// 短信验证码登录（需账号已绑定手机）。与密码登录分开展示，避免误进「无密码」界面。
class OtpLoginPage extends ConsumerStatefulWidget {
  const OtpLoginPage({super.key});

  @override
  ConsumerState<OtpLoginPage> createState() => _OtpLoginPageState();
}

class _OtpLoginPageState extends ConsumerState<OtpLoginPage> {
  final _loginName = TextEditingController();
  final _code = TextEditingController();
  bool _busy = false;
  bool _otpSent = false;
  String? _error;

  @override
  void dispose() {
    _loginName.dispose();
    _code.dispose();
    super.dispose();
  }

  bool get _canSubmit => !_busy && _loginName.text.trim().isNotEmpty && _code.text.trim().isNotEmpty;

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

  @override
  Widget build(BuildContext context) {
    final canSubmit = _canSubmit;
    return Scaffold(
      appBar: AppBar(title: const Text('验证码登录'), leading: BackButton(onPressed: () => context.go('/login'))),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('账号需已在「我的」里绑定并验证手机号', style: TextStyle(fontSize: 12, color: AppColors.gray)),
                const SizedBox(height: 16),
                TextField(
                  controller: _loginName,
                  decoration: const InputDecoration(labelText: '登录名', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                ),
                const SizedBox(height: 12),
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(
                    child: TextField(
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
                      onPressed: _busy || _loginName.text.trim().isEmpty
                          ? null
                          : () => _run(() async {
                                await ref.read(sessionProvider.notifier).sendOtp(_loginName.text);
                                if (mounted) setState(() => _otpSent = true);
                              }),
                      child: Text(_otpSent ? '重新发送' : '发送验证码'),
                    ),
                  ),
                ]),
                if (_otpSent)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text('验证码已发送到该账号绑定的手机', style: TextStyle(fontSize: 12, color: AppColors.gray)),
                  ),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 20),
                FilledButton(onPressed: canSubmit ? _submit : null, child: const Text('登录')),
              ]),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _submit() => _run(() => ref.read(sessionProvider.notifier).otpLogin(_loginName.text, _code.text));
}
