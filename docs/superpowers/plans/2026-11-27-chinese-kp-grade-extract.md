# 语文课内知识点按年级抽取 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 语文课内提取只产出知识点+课文（按年级三档侧重）；词表恒空，由册末回填。

**Architecture:** 在 `lesson_extract.py` 增加年级档位与语文专用 prompt 构建；`extract_lesson_content` 对语文强制 `words=[]`；`_run_extract` 传入 `PdfDocument.grade`。

**Tech Stack:** FastAPI / SQLAlchemy / pytest

---

### Task 1: 年级档位 + 语文 prompt 构建（纯函数）

**Files:**
- Create: `backend/tests/test_chinese_kp_extract.py`
- Modify: `backend/app/services/lesson_extract.py`

- [ ] **Step 1: 写失败测试** — `grade_band(1)=="1-2"`, `grade_band(4)=="3-4"`, `grade_band(6)=="5-6"`, `grade_band(None)=="3-4"`；`build_chinese_kp_prompt` 含白名单与对应侧重、不含「识字：」「写字：」「词语：」段要求
- [ ] **Step 2: 跑测确认失败**
- [ ] **Step 3: 实现 `grade_band` + `build_chinese_kp_prompt`**
- [ ] **Step 4: 跑测通过并提交**

### Task 2: `extract_lesson_content` 语文强制空词表

**Files:**
- Modify: `backend/tests/test_chinese_kp_extract.py`
- Modify: `backend/app/services/lesson_extract.py`

- [ ] **Step 1: 写失败测试** — fake provider 下语文返回 `words==[]`；AI 返回含「生词：」时解析后仍 `words==[]`
- [ ] **Step 2: 跑测确认失败**
- [ ] **Step 3: 语文走新 prompt；返回前清空 words；fallback 语文不抽词**
- [ ] **Step 4: 跑测通过并提交**

### Task 3: `_run_extract` 传入 grade

**Files:**
- Modify: `backend/app/routers/pdf.py`
- Modify: `backend/tests/test_fk_cleanup.py` 或新增测（mock 断言 grade 传入）

- [ ] **Step 1: 写失败测试** — extract 调用带上 document.grade
- [ ] **Step 2: 实现传入 `doc.grade`**
- [ ] **Step 3: 回归 `test_chinese_back_matter` + 相关 extract 测**
- [ ] **Step 4: 提交**
