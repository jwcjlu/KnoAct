import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../center/speech_player.dart';
import '../dictation_controller.dart';
import '../paper_dictation_controller.dart';

class DictationPaperFlow extends ConsumerStatefulWidget {
  const DictationPaperFlow({required this.base, required this.modeLabel, super.key});

  final DictationState base;
  final String modeLabel;

  @override
  ConsumerState<DictationPaperFlow> createState() => _DictationPaperFlowState();
}

class _DictationPaperFlowState extends ConsumerState<DictationPaperFlow> {
  bool _bootstrapped = false;
  final _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  void _bootstrap() {
    if (_bootstrapped) return;
    _bootstrapped = true;
    ref.read(paperDictationControllerProvider.notifier).bootstrap(
          taskId: widget.base.taskId,
          title: widget.base.title,
          subject: widget.base.subject,
          words: widget.base.words,
        );
  }

  Future<void> _pickPhoto({required void Function(String base64) onPicked}) async {
    final xfile = await _picker.pickImage(source: ImageSource.camera, imageQuality: 88);
    if (xfile == null) {
      final gallery = await _picker.pickImage(source: ImageSource.gallery, imageQuality: 88);
      if (gallery == null) return;
      final bytes = await gallery.readAsBytes();
      onPicked(base64Encode(bytes));
      return;
    }
    final bytes = await xfile.readAsBytes();
    onPicked(base64Encode(bytes));
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(paperDictationControllerProvider);
    final ctl = ref.read(paperDictationControllerProvider.notifier);

    if (widget.base.words.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.base.title.isEmpty ? '生词听写' : widget.base.title), backgroundColor: AppColors.bg),
        body: const Center(child: Text('当前词库暂无生词', style: TextStyle(color: AppColors.gray))),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.base.title.isEmpty ? '生词听写' : widget.base.title),
        backgroundColor: AppColors.bg,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(child: Text(widget.modeLabel, style: const TextStyle(fontSize: 12, color: AppColors.gray))),
          ),
        ],
      ),
      body: switch (s.phase) {
        PaperDictationPhase.listen || PaperDictationPhase.rewrite => _listenBody(context, s, ctl),
        PaperDictationPhase.upload => _uploadBody(context, ctl),
        PaperDictationPhase.grading => const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            CircularProgressIndicator(),
            SizedBox(height: 12),
            Text('正在批改…', style: TextStyle(color: AppColors.gray)),
          ])),
        PaperDictationPhase.result => _resultBody(context, s, ctl),
        PaperDictationPhase.finishGate => _finishGateBody(context, s, ctl),
        PaperDictationPhase.done => _doneBody(context, s),
      },
    );
  }

  Widget _listenBody(BuildContext context, PaperDictationState s, PaperDictationController ctl) {
    final total = s.rewriting ? s.wrong.length : s.words.length;
    final pos = s.rewriting ? s.rewriteIdx + 1 : s.idx + 1;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(s.rewriting ? '错词重写（$pos/$total）' : '听写（$pos/$total）',
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        const SizedBox(height: 16),
        SectionCard(
          child: Column(children: [
            FilledButton.icon(
              onPressed: () {
                final t = ctl.speakText();
                if (t == null) return;
                ref.read(speechPlayerProvider).speak(t).catchError((Object _) {
                  if (context.mounted) showMessage(context, '播放失败');
                });
              },
              icon: const Icon(Icons.volume_up),
              label: const Text('听发音'),
            ),
            const SizedBox(height: 8),
            const Text(
              '点击播放，在纸上写下你听到的词',
              style: TextStyle(color: AppColors.gray, height: 1.5),
            ),
            const SizedBox(height: 8),
            if (ctl.hintText() != null)
              Text(ctl.hintText()!, style: const TextStyle(color: AppColors.blue, fontWeight: FontWeight.w600))
            else
              TextButton(onPressed: ctl.hint, child: const Text('看提示')),
          ]),
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: ctl.advanceListen,
          child: Text(pos >= total ? '全部听完，去拍照' : '下一个词'),
        ),
      ],
    );
  }

  Widget _uploadBody(BuildContext context, PaperDictationController ctl) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('请在本子上写完后再拍照', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        const SizedBox(height: 12),
        const Text('对准整页听写内容，光线充足', style: TextStyle(color: AppColors.gray)),
        const Spacer(),
        FilledButton.icon(
          onPressed: () async {
            await _pickPhoto(onPicked: (b64) async {
              ctl.beginGrading(b64);
              await ctl.runGrading();
              if (context.mounted && ref.read(paperDictationControllerProvider).phase == PaperDictationPhase.upload) {
                showMessage(context, '批改失败，请重新拍照');
              }
            });
          },
          icon: const Icon(Icons.photo_camera),
          label: const Text('拍照上传'),
        ),
        const SizedBox(height: 40),
      ]),
    );
  }

  Widget _resultBody(BuildContext context, PaperDictationState s, PaperDictationController ctl) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('写对 ${s.correct} 个 · 错 ${s.wrong.length} 个',
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
        const SizedBox(height: 16),
        for (final w in s.wrong)
          SectionCard(
            child: ListTile(
              title: Text('标准：${w.word}'),
              subtitle: Text('你写的：${w.written.isEmpty ? "（未识别）" : w.written}'),
              trailing: TextButton(onPressed: () => ctl.appealWord(w), child: const Text('申诉')),
            ),
          ),
        const SizedBox(height: 16),
        if (s.wrong.isNotEmpty)
          FilledButton(onPressed: ctl.startRewrite, child: const Text('错词重写')),
        if (s.wrong.isEmpty)
          FilledButton(onPressed: ctl.goFinishGate, child: const Text('完成听写')),
        if (s.wrong.isNotEmpty) ...[
          const SizedBox(height: 8),
          OutlinedButton(onPressed: ctl.goFinishGate, child: const Text('跳过重写，完成听写')),
        ],
      ],
    );
  }

  Widget _finishGateBody(BuildContext context, PaperDictationState s, PaperDictationController ctl) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('打卡上传', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
        const SizedBox(height: 8),
        const Text('上传听写照片后提交任务，等待家长确认积分', style: TextStyle(color: AppColors.gray)),
        const Spacer(),
        FilledButton(
          onPressed: s.busy
              ? null
              : () async {
                  final okComplete = await ctl.completeDictation();
                  if (!context.mounted) return;
                  if (!okComplete) {
                    showMessage(context, '完成听写失败，请重试');
                    return;
                  }
                  final bytes = ctl.gradeImageBytes();
                  if (bytes == null) {
                    showMessage(context, '没有可上传的照片');
                    return;
                  }
                  final ok = await ctl.finishCheckIn(bytes: bytes);
                  if (!context.mounted) return;
                  if (!ok) showMessage(context, '上传或提交失败，请重试');
                },
          child: Text(s.busy ? '提交中…' : '用批改照片打卡并提交'),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: s.busy
              ? null
              : () async {
                  await _pickPhoto(onPicked: (b64) async {
                    final okComplete = await ctl.completeDictation();
                    if (!context.mounted || !okComplete) return;
                    try {
                      final bytes = base64Decode(b64);
                      final ok = await ctl.finishCheckIn(bytes: bytes);
                      if (context.mounted && !ok) showMessage(context, '上传或提交失败');
                    } catch (_) {
                      if (context.mounted) showMessage(context, '图片无效');
                    }
                  });
                },
          child: const Text('重新拍摄打卡照'),
        ),
        const SizedBox(height: 40),
      ]),
    );
  }

  Widget _doneBody(BuildContext context, PaperDictationState s) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(children: [
        const SizedBox(height: 32),
        const Icon(Icons.emoji_events, size: 56, color: AppColors.gold),
        const SizedBox(height: 12),
        const Text('听写打卡完成！', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Text('写对 ${s.correct} 个', style: const TextStyle(color: AppColors.green, fontWeight: FontWeight.w700)),
        const SizedBox(height: 24),
        FilledButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('返回')),
      ]),
    );
  }
}
