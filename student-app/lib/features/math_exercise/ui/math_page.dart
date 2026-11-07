import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../data/math_models.dart';
import '../math_controller.dart';

class MathPage extends ConsumerStatefulWidget {
  const MathPage({super.key});

  @override
  ConsumerState<MathPage> createState() => _MathPageState();
}

class _MathPageState extends ConsumerState<MathPage> {
  final _picker = ImagePicker();

  Future<void> _pickWordPhoto(int wordIndex) async {
    final ctl = ref.read(mathControllerProvider.notifier);
    var file = await _picker.pickImage(source: ImageSource.camera, imageQuality: 88);
    file ??= await _picker.pickImage(source: ImageSource.gallery, imageQuality: 88);
    if (file == null || !mounted) return;
    final bytes = await file.readAsBytes();
    final name = file.name.isNotEmpty ? file.name : 'math_word_$wordIndex.jpg';
    await ctl.uploadWordPhoto(wordIndex, bytes, filename: name);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(mathControllerProvider);
    final ctl = ref.read(mathControllerProvider.notifier);

    if (s.loading) {
      return Scaffold(
        appBar: AppBar(title: Text(s.title.isEmpty ? '数学练习' : s.title), backgroundColor: AppColors.bg, scrolledUnderElevation: 0),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final empty = !s.hasCalc && !s.hasWord;
    return Scaffold(
      appBar: AppBar(title: Text(s.title.isEmpty ? '数学练习' : s.title), backgroundColor: AppColors.bg, scrolledUnderElevation: 0),
      body: empty
          ? const Center(child: Text('本次数学练习暂无题目', style: TextStyle(color: AppColors.gray)))
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (s.error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(s.error!, style: const TextStyle(color: Colors.orange, fontSize: 13)),
                  ),
                if (s.detail.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(s.detail, style: const TextStyle(color: AppColors.gray, fontSize: 13)),
                  ),
                if (s.hasCalc) ...[
                  const Text('计算题', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 8),
                  if (!s.calcGraded)
                    Text(
                      '已填写 ${s.calcAnswers.where((a) => a.trim().isNotEmpty).length} / ${s.calc.length}',
                      style: const TextStyle(color: AppColors.gray, fontSize: 13),
                    ),
                  const SizedBox(height: 8),
                  for (var i = 0; i < s.calc.length; i++) ...[
                    _CalcCard(
                      index: i,
                      item: s.calc[i],
                      answer: i < s.calcAnswers.length ? s.calcAnswers[i] : '',
                      graded: s.calcGraded,
                      onChanged: s.calcGraded || s.submitted ? null : (v) => ctl.setCalcAnswer(i, v),
                    ),
                    const SizedBox(height: 12),
                  ],
                  if (s.canGradeCalc)
                    FilledButton(
                      onPressed: s.busy ? null : ctl.gradeCalc,
                      child: Text(s.busy ? '正在判分…' : '判分计算题'),
                    ),
                  if (s.calcResult != null) ...[
                    const SizedBox(height: 12),
                    _CalcSummary(result: s.calcResult!),
                  ],
                  const SizedBox(height: 20),
                ],
                if (s.hasWord) ...[
                  const Text('应用题', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 4),
                  const Text('在纸上写好过程与答案，每题拍一张照片', style: TextStyle(color: AppColors.gray, fontSize: 12)),
                  const SizedBox(height: 12),
                  for (final w in s.word) ...[
                    _WordCard(
                      item: w,
                      busy: s.busy,
                      locked: s.submitted,
                      onPhoto: () => _pickWordPhoto(w.index),
                    ),
                    const SizedBox(height: 12),
                  ],
                ],
                if (s.submitted)
                  const SectionCard(
                    child: Column(
                      children: [
                        Icon(Icons.hourglass_top, size: 36, color: AppColors.gray),
                        SizedBox(height: 8),
                        Text('已提交，等待家长确认', style: TextStyle(fontWeight: FontWeight.w600)),
                      ],
                    ),
                  )
                else if (s.canSubmit)
                  FilledButton(
                    onPressed: s.busy ? null : ctl.submit,
                    child: Text(s.busy ? '正在提交…' : '提交给家长确认'),
                  )
                else if (s.hasCalc || s.hasWord)
                  Text(
                    _submitHint(s),
                    style: const TextStyle(color: AppColors.gray, fontSize: 13),
                  ),
              ],
            ),
    );
  }

  String _submitHint(MathState s) {
    if (s.hasCalc && !s.calcGraded) return '请先完成计算题判分';
    if (s.hasWord && s.word.any((w) => !w.hasPhoto)) return '请为每道应用题拍照上传';
    if (s.hasWord && s.word.any((w) => !w.aiFinished)) return '应用题批改中，请稍候';
    return '完成全部题目后可提交';
  }
}

class _CalcCard extends StatelessWidget {
  const _CalcCard({
    required this.index,
    required this.item,
    required this.answer,
    required this.graded,
    required this.onChanged,
  });

  final int index;
  final MathCalcItem item;
  final String answer;
  final bool graded;
  final ValueChanged<String>? onChanged;

  @override
  Widget build(BuildContext context) {
    final res = item.isCorrect;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${index + 1}. ${item.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (!graded)
          TextField(
            key: ValueKey('math-calc-$index-${answer.hashCode}'),
            decoration: const InputDecoration(hintText: '输入答案（只写数字）', isDense: true, border: OutlineInputBorder()),
            keyboardType: TextInputType.number,
            onChanged: onChanged,
          )
        else
          Text(
            res == true ? '回答正确' : '回答有误，请订正后问家长或老师',
            style: TextStyle(color: res == true ? AppColors.green : Colors.red, fontWeight: FontWeight.w600),
          ),
      ]),
    );
  }
}

class _CalcSummary extends StatelessWidget {
  const _CalcSummary({required this.result});

  final MathGradeResult result;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text('计算题正确 ${result.correct}/${result.total}',
              style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.green)),
        ],
      ),
    );
  }
}

class _WordCard extends StatelessWidget {
  const _WordCard({required this.item, required this.busy, required this.locked, required this.onPhoto});

  final MathWordItem item;
  final bool busy;
  final bool locked;
  final VoidCallback onPhoto;

  @override
  Widget build(BuildContext context) {
    final status = mathWordStatusLabel(item);
    final canPhoto = !locked && !busy && (item.parentStatus == 'rejected' || !item.hasPhoto || !item.aiFinished);
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${item.index + 1}. ${item.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Text(status, style: TextStyle(color: _statusColor(status), fontWeight: FontWeight.w600, fontSize: 13)),
        if (canPhoto) ...[
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: onPhoto,
            icon: const Icon(Icons.photo_camera_outlined, size: 20),
            label: Text(item.hasPhoto && item.parentStatus == 'rejected' ? '重新拍照' : '拍照上传'),
          ),
        ],
      ]),
    );
  }

  Color _statusColor(String status) {
    if (status.contains('重新')) return Colors.orange;
    if (status.contains('等待') || status.contains('批改')) return AppColors.gray;
    if (status.contains('已确认')) return AppColors.green;
    return AppColors.gray;
  }
}
