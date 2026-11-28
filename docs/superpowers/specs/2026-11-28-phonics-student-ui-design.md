# 自然拼读学生端 UI（方案 A）设计

日期：2026-11-28  
状态：自审通过，按此实现

## 目标

让孩子在 Flutter 学生端按推荐路径浏览规则卡，并跟听规则音 / 例词音。  
**不做**练习判定、每日任务、掌握度、家长端。

## 决策

| 项 | 选择 | 理由 |
| --- | --- | --- |
| 形态 | 方案 A：学一学（浏览 + 跟听） | 内容已齐；最短可用路径 |
| 数据 | 打包 `catalog.json` + `audio/` 为 App 资源 | 不改后端；与 content/phonics 同源 |
| 入口 | 首页独立卡片（同「讲一遍」） | 不进每日任务，避免与识记宣称混淆 |
| 导航 | 七阶段列表 → 规则列表 → 规则详情（播音） | 对齐 path.yaml；目录查找二期再加 |
| 播放 | `audioplayers` AssetSource | 项目已有依赖 |
| 宣称 | 仅「跟读示范」 | 原料层，不宣称会用词 |

## 信息架构

```
首页「自然拼读」
  └─ 阶段 1…7（path.yaml）
       └─ 规则行：grapheme · IPA · 中文近似
            └─ 详情：播规则音；例词列表可逐词播
```

## 资源管线

1. `content/phonics/tools/export_flutter_catalog.py` 生成 `catalog.json`  
2. 同脚本把 `audio/rule`、`audio/word` 同步到 `student-app/assets/phonics/`  
3. `pubspec.yaml` 声明上述目录  

改 `rules.yaml` 后须重跑导出再编 App。

## 非目标

- 听辨 / 拼读练习与判分  
- 后端 API / Task / WordMastery  
- 字母多读法索引页（数据已有，UI 二期）  

## 自审

- 学习原理：原料层跟听，无「掌握」百分比 ✓  
- 与一期 id 一致，日后练习可挂同一批 id ✓  
- 资产约 8MB，可接受 ✓  
- Web/Android 均走 AssetSource；缺文件时按钮禁用并提示 ✓  
