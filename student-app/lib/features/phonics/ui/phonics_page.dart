import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../data/phonics_catalog.dart';
import '../data/phonics_repository.dart';
import '../phonics_audio_player.dart';

/// 自然拼读：按推荐路径浏览规则并跟听（不做练习判定）。
class PhonicsPage extends ConsumerWidget {
  const PhonicsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(phonicsCatalogProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('自然拼读')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('加载失败：$e')),
        data: (catalog) => _PhonicsBody(catalog: catalog),
      ),
    );
  }
}

class _PhonicsBody extends StatefulWidget {
  const _PhonicsBody({required this.catalog});
  final PhonicsCatalog catalog;

  @override
  State<_PhonicsBody> createState() => _PhonicsBodyState();
}

class _PhonicsBodyState extends State<_PhonicsBody> {
  int _stageIndex = 0;

  @override
  Widget build(BuildContext context) {
    final stages = widget.catalog.stages;
    if (stages.isEmpty) {
      return const Center(child: Text('暂无学习路径'));
    }
    final stage = stages[_stageIndex.clamp(0, stages.length - 1)];
    final rules = widget.catalog.rulesInStage(stage);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Text(
            '跟听示范 · 不记掌握度',
            style: TextStyle(fontSize: 13, color: AppColors.gray),
          ),
        ),
        SizedBox(
          height: 44,
          child: ListView.separated(
            key: const ValueKey('phonics-stage-tabs'),
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: stages.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, i) {
              final selected = i == _stageIndex;
              return ChoiceChip(
                key: ValueKey('phonics-stage-${stages[i].id}'),
                label: Text('第${stages[i].id}阶段'),
                selected: selected,
                onSelected: (_) => setState(() => _stageIndex = i),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Text(
            stage.name,
            key: const ValueKey('phonics-stage-title'),
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
        ),
        Expanded(
          child: rules.isEmpty
              ? const Center(child: Text('本阶段暂无规则'))
              : ListView.separated(
                  key: const ValueKey('phonics-rule-list'),
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: rules.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final rule = rules[i];
                    return Card(
                      child: ListTile(
                        key: ValueKey('phonics-rule-${rule.id}'),
                        title: Text(
                          rule.grapheme,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 18,
                          ),
                        ),
                        subtitle: Text(
                          [
                            if (rule.ipa.isNotEmpty) rule.ipa,
                            if (rule.approxZh.isNotEmpty) rule.approxZh,
                          ].join(' · '),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _openRule(context, rule),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  void _openRule(BuildContext context, PhonicsRule rule) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PhonicsRuleDetailPage(rule: rule),
      ),
    );
  }
}

class PhonicsRuleDetailPage extends ConsumerStatefulWidget {
  const PhonicsRuleDetailPage({super.key, required this.rule});
  final PhonicsRule rule;

  @override
  ConsumerState<PhonicsRuleDetailPage> createState() =>
      _PhonicsRuleDetailPageState();
}

class _PhonicsRuleDetailPageState extends ConsumerState<PhonicsRuleDetailPage> {
  String? _playing;
  String? _error;

  Future<void> _play(String path) async {
    if (path.isEmpty) {
      setState(() => _error = '暂无音频');
      return;
    }
    setState(() {
      _error = null;
      _playing = path;
    });
    try {
      await ref.read(phonicsAudioPlayerProvider).playAsset(path);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '播放失败';
        _playing = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final rule = widget.rule;
    final title = rule.grapheme;
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            rule.ipa.isEmpty ? '意识层（听例词）' : rule.ipa,
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
          ),
          if (rule.approxZh.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(rule.approxZh, style: const TextStyle(color: AppColors.gray)),
          ],
          if (rule.notes.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(rule.notes, style: const TextStyle(fontSize: 13)),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            key: const ValueKey('phonics-play-rule'),
            onPressed: () => _play(rule.ruleAudio),
            icon: Icon(
              _playing == rule.ruleAudio ? Icons.volume_up : Icons.play_arrow,
            ),
            label: const Text('听规则音'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 24),
          const Text(
            '例词',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          ...rule.exampleWords.map((w) {
            return Card(
              child: ListTile(
                key: ValueKey('phonics-word-${w.word}'),
                title: Text(w.word),
                subtitle: Text('年级 ${w.grades.join("/")}'),
                trailing: IconButton(
                  icon: Icon(
                    _playing == w.audio ? Icons.volume_up : Icons.play_circle,
                  ),
                  onPressed: () => _play(w.audio),
                ),
              ),
            );
          }),
          const SizedBox(height: 16),
          const Text(
            '跟听即可，系统不判定对错、不记掌握度。',
            style: TextStyle(fontSize: 12, color: AppColors.gray),
          ),
        ],
      ),
    );
  }
}
