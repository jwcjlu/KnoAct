# 自然拼读 GPC 规则库（content/phonics）

本目录是 KnoAct 英音自然拼读的**结构化规则库**：`rules.yaml` 为唯一权威数据源，配套学习路径、家长手册、音频清单与合成脚本。当前面向**家庭自用**；产品化上线前须按下文替换有版权风险的音频。

## 目录与推荐学习路径

| 文件 / 目录 | 用途 |
| --- | --- |
| `rules.yaml` | 全部 GPC 条目（字形、IPA、`path_order`、例词、音频路径与 `source`） |
| `path.yaml` | 阶段 1–7 的推荐学习顺序（`path_order_min` / `path_order_max`） |
| `handbook.md` | 由工具生成的家长可读手册（**勿手改**，改 `rules.yaml` 后重生成） |
| `letter_sounds_index.md` / `.yaml` | 字母 a/e/i/o/u/y **多种读法总览**（查阅用，不改学习路径） |
| `audio_manifest.yaml` | 规则音 / 例词音的期望路径与 `exists` 状态 |
| `audio/rule/` | 每条规则的示范音（优先外部音源；缺省再 TTS） |
| `audio/word/` | 例词音（TTS 或教材导出，**已入库**） |
| `vendor/openlettersounds/` | [Open Letter Sounds](https://purplecomputerorg.github.io/openlettersounds/) CC0 原包 |
| `vendor/vocamax-ipa/` | [vocamax/ipa-audios](https://github.com/vocamax/ipa-audios) IPA 音素包（见 ATTRIBUTION.md） |
| `tools/` | 生成、清单、合成、外部音源导入脚本 |
| `tests/` | schema、覆盖、生成物一致性测试 |

**怎么用「目录」vs「路径」：**

- **按类别浏览**：看 `handbook.md` 末尾「按类别索引」，或在 `rules.yaml` 里搜 `category`。
- **按推荐顺序学**：按 `path.yaml` 阶段 1→7 与 `path_order` 递增推进。
- **改内容**：只改 `rules.yaml`（必要时改 `path.yaml`），再跑测试与生成命令。

## 读音以音标为准

- **IPA（`ipa`）是权威读音**；`approx_zh` 仅为中文近似。
- 口音标记：`accent: oxford_shanghai`（教材取向）；外部音源多为美式纯音素，差异见各条 `notes`。
- 短元音约定：`a=/æ/` `e=/e/` `i=/ɪ/` `o=/ɒ/` `u=/ʌ/`。

## 校验

```bash
python -m pytest content/phonics/tests -v
```

## 常用命令

在仓库根目录（或 worktree 根）：

```bash
# 家长手册
python content/phonics/tools/generate_handbook.py \
  --rules content/phonics/rules.yaml \
  --path content/phonics/path.yaml \
  --out content/phonics/handbook.md

# 音频清单
python content/phonics/tools/generate_manifest.py \
  --rules content/phonics/rules.yaml \
  --audio-root content/phonics/audio \
  --out content/phonics/audio_manifest.yaml

# 字母主音：Open Letter Sounds（CC0）
python content/phonics/tools/import_openlettersounds.py --root content/phonics

# 字母多种读法总览
python content/phonics/tools/generate_letter_index.py

# 字母多种读法总览（查阅索引）
python content/phonics/tools/generate_letter_index.py

# digraph / 元音组合等：vocamax IPA（CC BY）
python content/phonics/tools/import_vocamax_ipa.py --root content/phonics

# 例词真音（讯飞 TTS → audio/word/<word>.wav，可提交入库）
python content/phonics/tools/synthesize_word_audio.py --root content/phonics

# 仅 source=tts 且缺失的规则音：占位或真 TTS
python content/phonics/tools/synthesize_rule_audio.py --root content/phonics --fake
python content/phonics/tools/synthesize_rule_audio.py --root content/phonics --force --only <rule_id>
```

导入 / 合成后请再跑一遍 `generate_manifest.py`。

## 外部音源优先级

1. **openlettersounds（CC0）**：字母主音（`a e i o u` + 辅音）。`y` 作元音用 vocamax `/ɪ/`；`qu` 见 blend。
2. **vocamax_ipa（CC BY）**：digraph / 元音组合 / r 控制 / magic e 等，按 IPA 映射。
3. **tts**：开/闭音节意识、部分 r 控制等；例词批量合成也走 TTS。`--fake` 仅占位、不可跟读。
4. **blend_***：`qu`=`k+w`（OLS）；`tion`/`ture`=`sh|ch+er`（vocamax）。修复脚本：
   `python content/phonics/tools/repair_rule_audio.py --root content/phonics`

## 音频：家庭自用与产品化

- **家庭自用**：例词可 TTS 或教材导出到 `audio/word/`。
- **产品化**：`textbook` / `companion` 不得原样上架；`openlettersounds`（CC0）可用；`vocamax_ipa` 须保留署名并复核上游许可；`tts` 占位须换成合规音。

## Git 与体积

- `audio/rule/*` 与 `audio/word/*` 均可提交（规则音约 2MB；例词 TTS 约 6MB）。
- 产品化上线前仍须按上文替换有版权风险的 `textbook` / `companion` 音源。
