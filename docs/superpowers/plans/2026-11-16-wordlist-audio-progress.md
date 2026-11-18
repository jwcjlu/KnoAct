# 磨耳朵页 Word list 分组 + 音频进度条 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 磨耳朵页把 Word list 音频单独分组展示，并给 `AudioBar` 加可自由拖拽的进度条（回退/快进），磨耳朵页与阅读器两处自动生效。

**Architecture:** 纯前端改动，后端不动。`AudioBar` 订阅 `audioplayers` 的 `onPositionChanged`/`onDurationChanged` 流渲染 `Slider`，拖拽调 `seek`；`listening_page.dart` 的 `_AudioListView` 按 `unitLabel == "Word list"` 把 rows 拆成课文/单词表两组渲染。

**Tech Stack:** Flutter + Riverpod + audioplayers 6.8.1。

**设计文档：** `docs/superpowers/specs/2026-11-16-wordlist-audio-progress-design.md`

---

## 文件结构

- 修改 `student-app/lib/features/lesson_audio/models/lesson_audio.dart` —— 加分组纯函数 `splitAudioRows`。
- 修改 `student-app/lib/features/lesson_audio/ui/audio_bar.dart` —— 加进度条。
- 修改 `student-app/lib/features/lesson_audio/ui/listening_page.dart` —— 分组渲染。
- 修改 `student-app/test/features/lesson_audio/lesson_audio_test.dart` —— 分组纯函数单测。

---

## Task 1: 分组纯函数 `splitAudioRows`

**Files:**
- Modify: `student-app/lib/features/lesson_audio/models/lesson_audio.dart`
- Test: `student-app/test/features/lesson_audio/lesson_audio_test.dart`

- [ ] **Step 1: 写失败测试**

在 `student-app/test/features/lesson_audio/lesson_audio_test.dart` 追加：

```dart
test('splitAudioRows 把 Word list 拆到单词表组', () {
  final rows = [
    LessonAudio(id: 1, lessonId: 54, unitLabel: 'Unit 1', audioPath: 'a', marks: const []),
    LessonAudio(id: 2, lessonId: null, unitLabel: 'Word list', audioPath: 'b', marks: const []),
    LessonAudio(id: 3, lessonId: 56, unitLabel: 'Unit 3', audioPath: 'c', marks: const []),
  ];
  final (unit, wordList) = splitAudioRows(rows);
  expect(unit.map((a) => a.unitLabel).toList(), ['Unit 1', 'Unit 3']);
  expect(wordList.map((a) => a.unitLabel).toList(), ['Word list']);
});

test('splitAudioRows 无单词表时 wordList 为空', () {
  final rows = [
    LessonAudio(id: 1, lessonId: 54, unitLabel: 'Unit 1', audioPath: 'a', marks: const []),
  ];
  final (unit, wordList) = splitAudioRows(rows);
  expect(unit.length, 1);
  expect(wordList, isEmpty);
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat test test/features/lesson_audio/lesson_audio_test.dart`
Expected: FAIL（`splitAudioRows` 未定义）。

- [ ] **Step 3: 实现纯函数**

在 `student-app/lib/features/lesson_audio/models/lesson_audio.dart` 末尾追加：

```dart
/// 把音频拆成 (课文音频, 单词表音频) 两组；单词表按 unit_label == "Word list" 判定。
(List<LessonAudio>, List<LessonAudio>) splitAudioRows(List<LessonAudio> rows) {
  final unit = <LessonAudio>[];
  final wordList = <LessonAudio>[];
  for (final a in rows) {
    (a.unitLabel == 'Word list' ? wordList : unit).add(a);
  }
  return (unit, wordList);
}
```

- [ ] **Step 4: 运行确认通过**

Run: 同上命令。Expected: 全部通过（3 个既有 + 2 个新 = 5 个 test）。

- [ ] **Step 5: Commit**

```bash
git add student-app/lib/features/lesson_audio/models/lesson_audio.dart student-app/test/features/lesson_audio/lesson_audio_test.dart
git commit -m "feat(student-app): lesson_audio 分组纯函数 splitAudioRows"
```

---

## Task 2: AudioBar 加进度条

**Files:**
- Modify: `student-app/lib/features/lesson_audio/ui/audio_bar.dart`

- [ ] **Step 1: 改造 AudioBar**

把 `student-app/lib/features/lesson_audio/ui/audio_bar.dart` 整个 `_AudioBarState` 改造为监听播放进度并渲染 `Slider`。替换文件内容为：

```dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import '../models/lesson_audio.dart';

/// 单个教材音频的播放条：可拖拽进度，整段播，或按 marks 分段（点某段从 start_sec 起播）。
class AudioBar extends StatefulWidget {
  const AudioBar({super.key, required this.audio, required this.url});
  final LessonAudio audio;
  final String url;

  @override
  State<AudioBar> createState() => _AudioBarState();
}

class _AudioBarState extends State<AudioBar> {
  final _player = AudioPlayer();
  final List<StreamSubscription<dynamic>> _subs = [];
  bool _playing = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  @override
  void initState() {
    super.initState();
    _subs.add(_player.onPositionChanged.listen((d) {
      if (mounted) setState(() => _position = d);
    }));
    _subs.add(_player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _duration = d);
    }));
    _subs.add(_player.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playing = false);
    }));
  }

  @override
  void dispose() {
    for (final s in _subs) {
      s.cancel();
    }
    _player.dispose();
    super.dispose();
  }

  Future<void> _play({double fromSec = 0}) async {
    await _player.play(UrlSource(widget.url),
        position: Duration(milliseconds: (fromSec * 1000).round()));
    if (mounted) setState(() => _playing = true);
  }

  Future<void> _stop() async {
    await _player.stop();
    if (mounted) setState(() {
      _playing = false;
      _position = Duration.zero;
    });
  }

  Future<void> _seek(double sec) async {
    await _player.seek(Duration(milliseconds: (sec * 1000).round()));
    if (mounted) setState(() => _position = Duration(milliseconds: (sec * 1000).round()));
  }

  @override
  Widget build(BuildContext context) {
    final marks = widget.audio.marks;
    final totalMs = _duration.inMilliseconds;
    final posMs = _position.inMilliseconds.clamp(0, totalMs > 0 ? totalMs : 0);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(children: [
          const Icon(Icons.volume_up, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(widget.audio.unitLabel, maxLines: 1, overflow: TextOverflow.ellipsis)),
          IconButton(
            icon: Icon(_playing ? Icons.stop : Icons.play_arrow),
            onPressed: () => _playing ? _stop() : _play(),
          ),
        ]),
        if (totalMs > 0)
          Slider(
            value: posMs.toDouble(),
            max: totalMs.toDouble(),
            onChanged: _seek,
          ),
        if (marks.isNotEmpty)
          Wrap(spacing: 8, children: [
            for (final m in marks)
              ActionChip(label: Text(m.label), onPressed: () => _play(fromSec: m.startSec)),
          ]),
      ],
    );
  }
}
```

> `onPlayerComplete` 是 `audioplayers 6.8.1` 的 `Stream<void>`（播完自动回调）。若版本里实际名为 `onPlayerComplete`（非 `onComplete`），以已装版本为准；若两者皆无，用 `onPlayerStateChanged` 监听 `PlayerState.completed` 替代。执行时 `grep -n "onPlayerComplete\|onComplete" ~/AppData/Local/Pub/Cache/hosted/pub.dev/audioplayers-6.8.1/lib/src/audioplayer.dart` 确认。

- [ ] **Step 2: analyze 验证**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat analyze lib/features/lesson_audio/ui/audio_bar.dart`
Expected: No issues found.

- [ ] **Step 3: 全量测试**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat test`
Expected: 全部通过（186+）。

- [ ] **Step 4: Commit**

```bash
git add student-app/lib/features/lesson_audio/ui/audio_bar.dart
git commit -m "feat(student-app): AudioBar 加可拖拽进度条"
```

---

## Task 3: 磨耳朵页 Word list 分组渲染

**Files:**
- Modify: `student-app/lib/features/lesson_audio/ui/listening_page.dart`

- [ ] **Step 1: 改造 _AudioListView**

把 `student-app/lib/features/lesson_audio/ui/listening_page.dart` 的 `_AudioListView` 的 `data` 分支改为分组渲染。替换：

```dart
        data: (rows) {
          if (rows.isEmpty) {
            return const Center(child: Text('该教材还没有配套音频'));
          }
          final repo = ref.read(lessonAudioRepositoryProvider);
          final (unit, wordList) = splitAudioRows(rows);
          return ListView(children: [
            for (final a in unit) AudioBar(audio: a, url: repo.audioUrl(a.audioPath)),
            if (wordList.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 20, 16, 8),
                child: Text('单词表', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
              ),
              for (final a in wordList) AudioBar(audio: a, url: repo.audioUrl(a.audioPath)),
            ],
          ]);
        },
```

注意：`listening_page.dart` 已 `import '../lesson_audio_controller.dart';`，而 controller import 了 `models/lesson_audio.dart` 但**未 re-export**。因此需要在 `listening_page.dart` 顶部补一个 import 以使用 `splitAudioRows`：

```dart
import '../models/lesson_audio.dart';
```

（放在现有 import 附近，`import '../lesson_audio_controller.dart';` 之后。）

- [ ] **Step 2: analyze 验证**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat analyze lib/features/lesson_audio/ui/listening_page.dart`
Expected: No issues found.

- [ ] **Step 3: 全量测试**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat test`
Expected: 全部通过。

- [ ] **Step 4: Commit**

```bash
git add student-app/lib/features/lesson_audio/ui/listening_page.dart
git commit -m "feat(student-app): 磨耳朵页 Word list 单独分组展示"
```

---

## Task 4: 收尾验证

- [ ] **Step 1: 全量 flutter test + analyze**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat analyze && E:\dev\flutter\bin\flutter.bat test`
Expected: analyze 无 error；test 全绿。

- [ ] **Step 2: 对照设计文档核对**

核对 `docs/superpowers/specs/2026-11-16-wordlist-audio-progress-design.md`：
分组纯函数、AudioBar 进度条（自由拖拽 + 保留标记跳转）、磨耳朵页分组渲染、
后端零改动。列出未覆盖项（若有）。

---

## 自检记录（Self-Review）

- **Spec 覆盖**：分组纯函数（Task 1）→ 进度条（Task 2）→ 磨耳朵页分组渲染（Task 3）→ 收尾（Task 4）。全部设计章节有对应任务。
- **占位符扫描**：无 TBD/TODO；每个代码步骤含完整代码；`onPlayerComplete` 的版本差异已显式标注为执行时确认项。
- **类型一致性**：`splitAudioRows` 返回 `(List<LessonAudio>, List<LessonAudio>)` 的 record，Task 1 定义与 Task 3 解构 `final (unit, wordList)` 一致；`LessonAudio` 字段 `unitLabel`/`marks` 在两处一致；进度条 `_seek(double sec)` 与 `Slider.onChanged(double)` 签名一致。
