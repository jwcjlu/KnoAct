# 模型与服务配置层设计（阶段 1）

日期：2026-10-26
状态：已确认，待实现
范围：四阶段中的**阶段 1**，其余阶段见文末「后续阶段」

## 背景与目标

KnoAct 现在的 AI 配置是**一张扁平 KV 表** `ModelConfig`，靠 `ai_provider / ai_model / ai_key / ai_base_url` 这一组键驱动全部 AI 调用（对话、出题、课文提取、OCR、语音合成）。这带来三个具体问题：

1. **一个 Key 只能配一套**。想让孩子对话用强模型、后台批量出题用便宜快的模型，做不到。
2. **加一种用途就要加一组键**。`vision_model`、`tts_*` 已经是这样长出来的，再加搜索/嵌入会继续膨胀。
3. **设置页是两坨平铺的表单**，看不出「哪个角色在用哪个模型」。

本阶段借鉴 DeepTutor 的「模型与服务」架构，把配置改成 **7 个角色 + 可复用连接** 的形态：

```
提供方（连接：一套凭证 + 端点）
   ├── 语言模型      llm
   ├── 后台任务模型   task
   ├── 嵌入模型      embedding
   ├── 搜索          search
   ├── 语音          tts / stt
   └── 多模态生成     imagegen
```

**关键收益：密钥只在「提供方」录一次，所有角色共用。** 这对小学家长产品是硬需求——不能让家长为 7 个角色重复粘贴 7 次 Key。

## 明确不做（本阶段）

- 不改造「边读边问」六模式（阶段 2）
- 不做掌握度与精通之路（阶段 3）
- 不把嵌入 / 搜索 / 多模态接入真实业务（阶段 4，或永不）
- 不做 DeepTutor 的「草稿 / 已应用」双态、SSE 测试进度流、按用户隔离配置（`multi_user`）

## 数据模型

新增三张表，`ModelConfig` **保留不动**（继续存非凭证设置，如 `task_dictation_count`、`tts_speed`）。

```python
class ModelConnection(Base):
    """一套凭证 + 端点，可被多个角色复用。"""
    __tablename__ = "model_connections"
    id: int
    provider: str          # openai | deepseek | glm | minimax | xunfei | fake
    name: str              # 用户可见名，如「中转站主账号」
    base_url: str = ""
    api_key: str = ""      # 明文存储；API 出口一律打码
    extra_headers: str = ""  # JSON 文本，少数中转站需要
    created_at: datetime

class ModelProfile(Base):
    """某角色下的一档模型选择。"""
    __tablename__ = "model_profiles"
    id: int
    role: str              # llm|task|embedding|search|tts|stt|imagegen
    connection_id: int | None   # FK → model_connections，删除连接时置 NULL
    model: str = ""        # 如 deepseek-chat；search 可为空
    name: str = ""         # 显示名，空则回落到 model
    options: str = ""      # JSON：voice / speed / dimension / size / vision_model
    created_at: datetime

class RoleBinding(Base):
    """角色 → 当前启用哪一档。主键即 role。"""
    __tablename__ = "role_bindings"
    role: str              # 主键
    profile_id: int | None # 空 = 未配置
    mode: str = "inherit"  # 仅 task 使用：inherit | reference
```

**设计取舍：**

- **`RoleBinding` 单独建表**，不塞进 `ModelConfig`。`ModelConfig` 是用户可编辑的 KV，混入内部指针会让「哪些键是设置、哪些是状态」变得混乱；单独窄表还能用外键约束。
- **`options` 用 JSON 文本而非拆列**。7 个角色参数各不相同（embedding 要 `dimension`、tts 要 `voice`/`speed`、imagegen 要 `size`），拆列会产生 20 多列且大半闲置。
- **`connection_id` 可空**，允许「角色只选模型不配连接」的罕见情况（如搜索走内置通道）。
- **`provider` 白名单在代码里**，不建表——它是代码常量而非用户数据。

## 注册表与解析

### Provider 注册表（代码常量）

```python
@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    needs_base_url: bool
    default_model: str = ""

REGISTRY: dict[str, tuple[ProviderSpec, ...]] = {
    "llm":       (OPENAI, DEEPSEEK, GLM, FAKE),
    "task":      (OPENAI, DEEPSEEK, GLM, FAKE),
    "embedding": (OPENAI, FAKE),
    "search":    (OPENAI, FAKE),
    "tts":       (OPENAI, MINIMAX, XUNFEI, FAKE),
    "stt":       (OPENAI, FAKE),
    "imagegen":  (OPENAI, FAKE),
}
```

前端下拉由 `GET /api/config/catalog` 直接吐出，**删除 `frontend/app.js` 里硬编码的 `aiProviders` / `ttsProviders`**。

### 统一解析出口

```python
@dataclass(frozen=True)
class Resolved:
    role: str
    provider: str
    model: str
    base_url: str
    api_key: str
    extra_headers: dict
    options: dict
    source: str          # 'binding' | 'legacy' | 'default'

def resolve(db, role: str) -> Resolved
```

**三级降级链**（每一级都可观测，见 `source` 字段）：

1. `RoleBinding.profile_id` 存在 → 用该 profile 与其 connection，`source='binding'`
2. 否则读老键：`llm`→`ai_*`，`tts`→`tts_*`，`imagegen`→`vision_model`，`source='legacy'`
3. 都没有 → `fake` provider，`source='default'`

**绝不抛异常**，与现有 `FakeProvider` 的兜底行为一致。第 2 级是本阶段的**安全网**：新表为空时系统行为与改造前完全相同。

### `task` 继承 `llm`

`RoleBinding.mode`：

- `inherit`（默认）→ 解析 `llm`，不重复计费、不重复配置
- `reference` → 解析 `llm` 但允许单独覆盖 `model`

未配置 `task` 时自动跟随，不会因为「没配后台模型」而报错。

### 调用方零改动

`get_provider(db)` / `get_tts(db)` **签名不变**，内部改为 `r = resolve(db, 'llm')` / `resolve(db, 'tts')` 再拼装现有 Provider 类。因此 `notes.py`、`question_gen.py`、`lesson_extract.py`、`tts_router.py` 全部**一行不改**。

### OCR 的视觉模型

7 个角色里没有「视觉理解」（它是模型能力而非角色）。`ai.py::ocr_image` 现在读独立键 `vision_model`，改为读 **`llm` 档位 `options.vision_model`**，未设则回落老键，再没有则报错。不新增第 8 个角色。

## 接口设计

新增/改造均挂在 `/api/config` 下：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/config/catalog` | 返回 `{registry, connections, services}`，**密钥一律打码** |
| PUT | `/api/config/catalog` | 保存整个目录（连接 + 各角色档位 + 绑定） |
| POST | `/api/config/probe` | 凭据探针：`GET {base_url}/models`，返回状态与模型列表 |
| POST | `/api/config/test` | 按 `role` 分派真实调用测试（扩展现有接口） |
| GET/POST | `/api/config` | **保留不动**，扁平 KV 读写，老调用方依赖 |

### 密钥掩码

`MASK = "***"`，照搬 DeepTutor 的往返语义：

| 出口 | 行为 |
|---|---|
| `GET /catalog` | 非空 `api_key` → `"***"`；空串保持空串（区分「没配」与「配了」） |
| `PUT /catalog` | 收到 `"***"` → 沿用已存值；收到空串 → 清空；其它 → 更新 |
| 日志 / 错误 | 异常兜底过 `redact()`，防止 `str(e)` 带出 URL 里的 key |

**两个易错点：**

1. **新建连接时** key 输入框初始为空串而非 `"***"`。判定依据是「有无 `id`」：无 `id` 且值为 `MASK` → 视为空。
2. **删除连接时**，引用它的 profile 置 `connection_id=NULL`，不级联删除角色配置。

### 连通测试

**凭据探针 `POST /api/config/probe`**

```
{role, provider, base_url, api_key, extra_headers}
→ {status: connected|auth_error|unreachable|invalid_url|http_error|timeout,
   models: [{id}], warning?}
```

实现即 `GET {base_url}/models`。**注意顺序**：前端传来的 key 可能是 `"***"`，后端必须先 `restore` 换回真 key 再探测。

不实现 DeepTutor 的 `capabilities` 推断（模型能否看图/出 JSON）——6 个 provider 用不到自动推断。

**真实调用 `POST /api/config/test`**，按 `role` 分派：

| role | 动作 |
|------|------|
| `llm` | 发「请回复连接成功」 |
| `task` | 若为 `inherit` 直接返回 `{ok:true, note:"继承语言模型"}`，不重复计费 |
| `tts` | 合成「测试」二字，返回字节数 |
| `embedding` | 发一条极短文本取向量，返回维度 |
| `search` | 跑一次空查询，只验连通 |
| `imagegen` | 只校验字段完整，不生成 |
| `stt` | 不测，返回 `{ok:true, note:"未实现，跳过"}` |

**不加 SSE 进度流**：最慢是 embedding 取向量（约 2 秒），同步返回即可。

## 前端设计

设置页重构为 **左侧角色导航 + 右侧配置面板**，样式完全沿用现有 token（`--blue-soft`、`--line3`、`.parent-panel` 的 24px 圆角、`.btn-primary` 的 `--blue`），不引入新视觉风格。原型已改好可交互版本（`prototype/index.html`）。

### 布局

```
+-- 模型与服务 ---+-- 语言模型 ---------------------- [已配置] --+
| * 语言模型      |  对话、追问、讲解、出题                     |
| o 后台任务模型  |  提供方   [ DeepSeek 官方        v ]        |
|   嵌入模型 未接入|  模型     [ deepseek-chat        v ] [拉取模型]|
|   搜索    未接入|                                            |
| * 语音          |                          [测试连接] [保存配置]|
|   语音识别 未接入|  -- 当前生效配置 ---------------------------|
|   多模态   未接入|  语言模型      DeepSeek 官方 · deepseek-chat|
|                |  后台任务模型   跟随语言模型                  |
| ---------------|  语音         MiniMax 语音 · speech-01-turbo|
| 提供方          |                                            |
+----------------+--------------------------------------------+
```

（`*` = 已配置，`o` = 待选模型，空白 = 未配置；未接线角色显示「未接入」标签）

### 要点

- **左侧状态圆点**：绿=已配置、黄=待选模型、灰=未配置；未接线角色显示「未接入」灰标签。
- **`task` 角色**默认勾选「跟随语言模型（推荐）」，取消后才展开提供方与模型字段。
- **未接线角色**（embedding/search/stt/imagegen）显示提示：「该角色暂未接入业务，配置会保存，但不会影响现有功能。」
- **提供方页**：连接卡片列表，显示 provider 徽标、端点、掩码后的 Key，支持编辑 / 删除 / 新增。
- **语音角色**额外提供音色、语速、试听。
- **字段宽度限制**（`max-width: 560px`），避免宽屏下输入框拉成 1000px。

### 前端状态

新增 `catalog = {registry, connections, services}`，由 `/api/config/catalog` 一次拉全。旧的 `aiConfig` / `ttsConfig` 保留给对话页的模型选择 chip 使用，但改为**从 catalog 派生**，不再各自维护一份。

## 迁移

`backend/migrate_model_catalog.py`，幂等可重跑：

```
读 ModelConfig 老键
├─ ai_key 非空 或 ai_provider≠fake
│    → ModelConnection(provider=ai_provider, base_url=ai_base_url, api_key=ai_key)
│    → ModelProfile(role='llm', model=ai_model)
│    → RoleBinding('llm', profile_id)
├─ tts_key 非空 或 tts_provider≠fake
│    → 同上，role='tts'，options={voice, speed, model}
└─ vision_model 非空 → 写入 llm profile 的 options.vision_model
老键全部保留（不删），仅作 degrade 来源
```

**验收条件**：迁移后 `resolve()` 返回的 7 个角色结果与迁移前完全一致。脚本提供 `--verify` 模式，打印 `Resolved` 与老键对照，可肉眼核对。

## 灰度与回退

1. **新表为空时自动走 legacy 分支** → 不跑迁移也能正常用，风险为零。
2. **设置页「新版 / 旧版」切换开关** → 出问题时家长可退回旧表单。
3. **`/api/config` 扁平 KV 接口保留** → 老调用方不受影响。

## 测试

单元测试（`backend/tests/`）：

- `resolve()` 三级降级：binding / legacy / default 各一条
- `task` 继承：`inherit` 时返回 llm 的模型；`reference` 时返回自己的模型
- 密钥掩码往返：`redact` → `restore` 后 key 与原文一致
- 掩码边界：新建（无 `id`）时 `"***"` 视为空；删除连接后 profile 的 `connection_id` 为 `None`

迁移测试：

- 给定一组老键，迁移后 `resolve` 输出与老键一致
- 重复跑迁移不产生重复连接

## 后续阶段（不在本阶段实现）

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 2 | 边读边问六模式（统一能力注册表，每个模式=提示词+工具集） | 阶段 1 的 `resolve('llm')` / `resolve('task')` |
| 3 | 精通之路：双层掌握度（单词 + 知识点）+ 门槛判定 | 阶段 2 的测验结果作为证据 |
| 4 | 打通与打磨：掌握度接进错题本/任务生成/家长报告 | 阶段 3 |
