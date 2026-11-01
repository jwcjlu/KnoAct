import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../data/auth_repository.dart';
import '../session.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _name = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(sessionProvider.notifier).login(_name.text);
    } on NotAChildException {
      _error = '这个名字不是孩子账号，请输入孩子的名字';
    } catch (_) {
      _error = '登录失败，请检查网络或后端服务';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final canSubmit = !_busy && _name.text.trim().isNotEmpty;
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
                  controller: _name,
                  decoration: const InputDecoration(labelText: '你的名字', border: OutlineInputBorder()),
                  onChanged: (_) => setState(() => _error = null),
                  onSubmitted: (_) => canSubmit ? _submit() : null,
                ),
                const SizedBox(height: 8),
                const Text('首次使用会自动创建账号，请确认名字无误', style: TextStyle(fontSize: 12, color: AppColors.gray)),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 20),
                FilledButton(onPressed: canSubmit ? _submit : null, child: const Text('开始学习')),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
