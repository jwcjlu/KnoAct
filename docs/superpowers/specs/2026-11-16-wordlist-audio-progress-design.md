# 磨耳朵页 Word list 分组 + 音频进度条设计

日期：2026-11-16
状态：待评审

## 背景与目标

教材配套真人音频（上一步已实现）目前有两个体验缺口：

1. **Word list 混在 Unit 里**：`09_Word list.mp3`（整本单词表朗读）被当作普通音频
   条目和 Unit 1–8 平铺在一起，孩子无法把它作为「单词表」单独听。
2. **播放器没有进度条**：`AudioBar` 只有播放/停止 + 分段标记跳转，无法自由
   拖拽回退/快进重听某一段。

本次目标：把 Word list 拆成独立的「单词表」分组入口，并给所有音频播放器加
可自由拖拽的进度条。

## 决策记录（已与用户确认）

- **Word list 定位**：独立「单词表」播放入口（不做单词级切分/跟读，不做与
  WordBank 生词库打通）。
- **入口位置**：磨耳朵页内加分组（不加新页面、不加首页独立卡片）。
- **进度条范围**：所有播放器都加（磨耳朵页 + 阅读器内，两者共用 `AudioBar`）。
- **拖拽与标记**：自由拖拽到任意秒数，同时保留「点标记跳到每课起点」按钮，两者并存。
- **Word list 判定**：`unit_label == "Word list"`（后端已解析好；不做更灵活识别）。
- **进度条样式**：Flutter 自带 `Slider`。

## 现状

- `parse_unit_label("09_Word list.mp3")` 已返回 `"Word list"`，且
  `_match_lesson_by_label` 对 `"Word list"` 返回 `None`（`lesson_id=null`）。
- `AudioBar`（`student-app/lib/features/lesson_audio/ui/audio_bar.dart`）：只有
  `IconButton` 播放/停止 + `ActionChip` 分段标记，无进度条。
- `_AudioListView`（`listening_page.dart`）：`rows` 平铺成 `AudioBar` 列表，无分组。

## 设计

### 改动 1：磨耳朵页 Word list 分组

`_AudioListView`（`listening_page.dart`）把 `rows` 拆成两组：

- **课文音频**：`unit_label != "Word list"` 的条目。
- **单词表**：`unit_label == "Word list"` 的条目。

渲染：课文音频照旧平铺；若有单词表条目，在其下方加一个「单词表」分组标题
（分隔），再渲染单词表音频的 `AudioBar`。单词表为空则只显示课文部分（不显示
空标题）。

判定用 `unit_label == "Word list"`（`lesson_id == null` 等价，但用 unit_label
更直白、语义清晰）。

### 改动 2：AudioBar 加进度条

`AudioBar` 增加：

- 订阅 `AudioPlayer` 的 `onPositionChanged`（当前秒数）与 `onDurationChanged`
  （总时长）流，存入 state。
- 一个 `Slider`（`value` = 当前秒，`max` = 总时长），`onChanged` 时
  `_player.seek(Duration(seconds: value))`（可自由拖拽回退/快进）。
- 保留现有播放/停止按钮与 `ActionChip` 分段标记跳转。

进度条仅在总时长 > 0 时显示。播放中拖拽后继续播放；停止状态拖拽仅改变播放位置
（`seek` 后仍为停止态，点播放从新位置开始）。

### 后端

**无需改动**。Word list 的 `unit_label` 与 `lesson_id=null` 已由后端解析好；
进度条是纯前端。

## 文件改动

- 修改 `student-app/lib/features/lesson_audio/ui/audio_bar.dart` —— 加进度条。
- 修改 `student-app/lib/features/lesson_audio/ui/listening_page.dart` —— 分组渲染。
- 新增/更新 `student-app/test/features/lesson_audio/lesson_audio_test.dart` ——
  分组纯函数（把 rows 拆成课文/单词表两组）单测。

## 测试

- 纯函数 `splitRows(List<LessonAudio>) -> (unit, wordList)` 单测：正常混合、
  仅课文、仅单词表、空。
- `AudioBar` 进度条：widget 测试覆盖 Slider 存在、seek 调用（如可 mock player）。

## 范围与非目标

**做**：磨耳朵页 Word list 分组 + AudioBar 进度条。

**不做**（后续）：单词级切分/跟读、WordBank 生词库打通、自定义进度条样式、
后端改动。
