# 自然拼读 GPC 规则库（content/phonics）

本目录是 KnoAct 英音自然拼读的**结构化规则库**：`rules.yaml` 为唯一权威数据源，配套学习路径、家长手册、音频清单与合成脚本。当前面向**家庭自用**；产品化上线前须按下文替换有版权风险的音频。

## 目录与推荐学习路径

| 文件 / 目录 | 用途 |
| --- | --- |
| `rules.yaml` | 全部 GPC 条目（字形、IPA、`path_order`、例词、音频路径与 `source`） |
| `path.yaml` | 阶段 1–7 的推荐学习顺序（`path_order_min` / `path_order_max`） |
| `handbook.md` | 由工具生成的家长可读手册（**勿手改**，改 `rules.yaml` 后重生成） |
| `audio_manifest.yaml` | 规则音 / 例词音的期望路径与 `exists` 状态 |
| `audio/rule/` | 每条规则的示范音（优先外部音源；缺省再 TTS / 占位） |
| `audio/word/` | 例词配套音（教材 / 配套 CD 等，**默认不入库**） |
| `vendor/openlettersounds/` | [Open Letter Sounds](https://purplecomputerorg.github.io/openlettersounds/) CC0 原包缓存 |
| `tools/` | 生成、清单、合成、外部音源导入脚本 |
| `tests/` | schema、覆盖、生成物一致性测试 |

**怎么用「目录」vs「路径」：**

- **按类别浏览**：看 `handbook.md` 末尾「按类别索引」，或直接在 `rules.yaml` 里搜 `category`（`vowel` / `consonant` / …）。
- **按推荐顺序学**：按 `path.yaml` 阶段 1→7 与 `path_order` 递增推进；手册前半部分已按阶段编排，与 `path.yaml` 一致。
- **改内容**：只改 `rules.yaml`（必要时改 `path.yaml`），再跑测试与生成命令（见下）。

## 读音以音标为准

- 每条规则的 **IPA（`ipa` 字段）是权威读音**；`approx_zh` 仅为帮助家长理解的**中文近似**，不能代替音标。
- 全库口音固定为 **`accent: oxford_shanghai`**（牛津上海版教材体系下的英式取向；与课堂教材一致为目标，非通用 RP 百科音）。
- **短元音 IPA 约定**（与 `rules.yaml` 一致，全库统一）：

  | 字母 | IPA |
  | --- | --- |
  | a | /æ/ |
  | e | /e/ |
  | i | /ɪ/ |
  | o | /ɒ/ |
  | u | /ʌ/ |

  元音字母 `y` 作元音时主音一般为 /ɪ/（如 happy 词尾）；具体变体见各条 `notes`。

## 校验

在仓库根目录执行（需已安装 `content/phonics/requirements.txt` 中的依赖）：

```bash
python -m pytest content/phonics/tests -v
```

## 生成手册、清单与规则音

在仓库根目录：

```bash
# 家长手册
python content/phonics/tools/generate_handbook.py \
  --rules content/phonics/rules.yaml \
  --path content/phonics/path.yaml \
  --out content/phonics/handbook.md

# 音频存在性清单
python content/phonics/tools/generate_manifest.py \
  --rules content/phonics/rules.yaml \
  --audio-root content/phonics/audio \
  --out content/phonics/audio_manifest.yaml

# 导入 Open Letter Sounds（CC0）到字母主音规则音
python content/phonics/tools/import_openlettersounds.py \
  --root content/phonics \
  --vendor content/phonics/vendor/openlettersounds

# 仅为仍缺失且 source=tts 的规则音写占位 WAV（无真实读音）
python content/phonics/tools/synthesize_rule_audio.py \
  --root content/phonics --fake
```

合成 / 导入后请**再跑一遍 manifest**。

### 外部音源优先级

1. **Open Letter Sounds（CC0）**：已挂到 25 条字母主音（`a e i o u` + 20 辅音，不含 `y`——OLS 的 y 是辅音 /j/，与本库 `vowel.y.short`=/ɪ/ 不同）。`source: openlettersounds`。美式纯音素；与沪教牛津英式有差异处见各条 `notes`。许可见 `vendor/openlettersounds/LICENSE`。
2. **Phonicademy 等 digraph / 元音组合包**：待导入时用 `source: phonicademy`（schema 已预留）。
3. **TTS / `--fake`**：仅补缺口；`--fake` **不含可跟读内容**。

## 音频：家庭自用与产品化边界

- **家庭自用**：可自行从教材、配套 CD、点读笔等导出例词读音，放入 `audio/word/`，文件名与 manifest 中 `expected_path` 一致（通常为 `audio/word/<word>.wav`），然后重新生成 `audio_manifest.yaml`。
- **产品化 / 对外发布**：凡 `source` 为 **`textbook`** / **`companion`** 的音频，必须换成有权分发的素材。`openlettersounds`（CC0）可继续用；`tts` 占位须换成合规 TTS 或录音。

## 例词配套音 workflow

1. 从合法来源导出单词 WAV（勿提交有版权争议的翻录到公开仓库，见 `.gitignore`）。
2. 放入 `content/phonics/audio/word/`（保留 `.gitkeep`）。
3. 重新执行上面的 `generate_manifest.py` 命令，检查对应 `examples[].exists`。

## Git 与体积

- `audio/word/*` 默认被根目录 `.gitignore` 忽略（仅保留 `.gitkeep`），避免误提交配套翻录。
- `audio/rule/*.wav` **可以提交**（含 `--fake` 生成的占位文件），以便克隆后 manifest 中规则音 `exists: true`。