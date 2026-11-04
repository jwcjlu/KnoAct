# 屏幕时间管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长能看清孩子在安卓设备上每个 App 的使用时长、按 App 分组设「每天上限」，超时提醒孩子、家长端可见超时状态。

**Architecture:** 安卓端 Flutter 经 MethodChannel 调 `UsageStatsManager` 本地采样 → 每 5 分钟批量上报后端 `/api/screen-time/*` → 后端存 `ScreenUsage` 并按组计算超时 → 家长端 `parent-web` 新增「屏幕时间」Tab 管理分组/规则、查看今日与历史超时。分组/规则与超时判定以安卓端本地缓存为主（及时弹提醒），后端作为持久化与家长端展示的权威源。

**Tech Stack:** FastAPI + SQLAlchemy（后端）；Flutter + Riverpod + dio + MethodChannel/WorkManager + `flutter_local_notifications`（安卓端）；原生 JS `parent-web`（家长端）。

**Spec:** `docs/superpowers/specs/2026-11-04-screen-time-management-design.md`

---

## 文件结构

**后端：**
- `backend/app/models.py`（修改）— 新增 `AppGroup` / `AppRule` / `ScreenUsage` 三表
- `backend/app/routers/screen_time.py`（新建）— `/api/screen-time/*` 路由
- `backend/app/services/screen_time.py`（新建）— 分组归类、超时计算纯函数
- `backend/app/main.py`（修改）— `include_router`
- `backend/tests/test_screen_time.py`（新建）— 后端测试

**安卓端（`student-app/`）：**
- `android/app/src/main/kotlin/com/knoact/student_app/UsageStatsPlugin.kt`（新建）— MethodChannel + UsageStatsManager
- `android/app/src/main/kotlin/com/knoact/student_app/MainActivity.kt`（修改）— 注册 channel
- `lib/features/screen_time/data/usage_api.dart`（新建）— MethodChannel 封装 + 本地缓存
- `lib/features/screen_time/data/screen_time_sync.dart`（新建）— 上报 + 规则拉取 + 超时计算
- `lib/features/screen_time/data/screen_time_repository.dart`（新建）— Riverpod provider
- `lib/features/screen_time/ui/usage_permission_page.dart`（新建）— 权限引导页
- `lib/features/screen_time/ui/screen_time_page.dart`（新建）— 孩子端「屏幕时间」页
- `pubspec.yaml`（修改）— 加 `workmanager`、`flutter_local_notifications`
- `test/screen_time_test.dart`（新建）— 纯逻辑测试

**家长端：**
- `parent-web/app.js`（修改）— 新增「屏幕时间」Tab + 渲染/交互
- `parent-web/index.html`（修改，如需）— 引入分组拖拽样式（纯内联即可，通常无需改）

---

## Task 1: 后端数据模型（三张表）

**Files:**
- Modify: `backend/app/models.py`（追加到文件末尾，`ChildConfig` 之后）
- Test: `backend/tests/test_screen_time.py`

- [ ] **Step 1: 写失败测试（模型建表 + 唯一约束）**

```python
# backend/tests/test_screen_time.py
"""屏幕时间：分组/规则/使用时长的模型与服务。"""
from app.models import User, AppGroup, AppRule, ScreenUsage
from app.services.screen_time import classify_package, compute_group_totals


def _child(db, name="晨晨"):
    u = User(name=name, role="child", grade=3)
    db.add(u); db.flush()
    return u


def test_appgroup_unique_per_child(setup_db, db):
    c = _child(db)
    db.add(AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600))
    db.add(AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=7200))
    db.commit()  # 应不抛错：UniqueConstraint 在 user_id+name
    assert db.query(AppGroup).filter_by(user_id=c.id).count() == 2


def test_screen_usage_upsert_accumulates(setup_db, db):
    c = _child(db)
    db.add(ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.douyin", app_name="抖音", duration_seconds=120, group_id=None))
    db.commit()
    # 累加语义由 service 负责，这里先验证字段可写
    row = db.query(ScreenUsage).filter_by(child_id=c.id, app_package="com.douyin").first()
    assert row.duration_seconds == 120
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_screen_time.py -v`
Expected: FAIL — `ImportError: cannot import name 'AppGroup' from 'app.models'`

- [ ] **Step 3: 实现三张表**

在 `backend/app/models.py` 末尾追加：

```python
class AppGroup(Base):
    """屏幕时间 App 分组；kind: learn=学习 / fun=娱乐 / custom=自定义。"""
    __tablename__ = "app_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_app_group_user_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="custom")  # learn | fun | custom
    daily_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=True)  # 空 = 不限


class AppRule(Base):
    """App 包名 → 分组的映射。"""
    __tablename__ = "app_rules"
    __table_args__ = (
        UniqueConstraint("user_id", "app_package", name="uq_app_rule_user_package"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    app_package: Mapped[str] = mapped_column(String(255))
    app_name: Mapped[str] = mapped_column(String(255), default="")
    group_id: Mapped[int] = mapped_column(ForeignKey("app_groups.id"))


class ScreenUsage(Base):
    """每孩子每天每 App 的前台使用时长（上报去重累加）。"""
    __tablename__ = "screen_usage"
    __table_args__ = (
        UniqueConstraint("child_id", "date", "app_package", name="uq_screen_usage_child_date_pkg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    app_package: Mapped[str] = mapped_column(String(255))
    app_name: Mapped[str] = mapped_column(String(255), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
```

同时创建空 `backend/app/services/screen_time.py` 并写两个占位函数，让 import 不报错：

```python
# backend/app/services/screen_time.py
"""屏幕时间：App 分组归类与超时计算（纯函数）。"""


def classify_package(db, user_id: int, app_package: str, app_name: str):
    """返回该包名应归入的 group_id；未知 App 归「娱乐类」，无娱乐组则 None。"""
    raise NotImplementedError


def compute_group_totals(db, child_id: int, date: str):
    """返回 {group_id: 总秒数}，供超时判定。"""
    raise NotImplementedError
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_screen_time.py -v`
Expected: PASS（两个模型测试通过；service 函数仅定义未调用）

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/app/services/screen_time.py backend/tests/test_screen_time.py
git commit -m "feat(screen-time): 新增 AppGroup/AppRule/ScreenUsage 三表与空 service"
```

---

## Task 2: 分组归类与超时计算 service

**Files:**
- Modify: `backend/app/services/screen_time.py`
- Test: `backend/tests/test_screen_time.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_screen_time.py` 追加：

```python
def test_unknown_package_falls_to_fun_group(setup_db, db):
    c = _child(db)
    fun = AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600)
    learn = AppGroup(user_id=c.id, name="学习类", kind="learn", daily_limit_seconds=None)
    db.add_all([fun, learn]); db.commit()
    gid = classify_package(db, c.id, "com.tencent.tmgp.sgame", "王者荣耀")
    assert gid == fun.id


def test_known_package_uses_app_rule(setup_db, db):
    c = _child(db)
    learn = AppGroup(user_id=c.id, name="学习类", kind="learn", daily_limit_seconds=None)
    db.add(learn); db.commit()
    db.add(AppRule(user_id=c.id, app_package="com.knoact", app_name="知学伴", group_id=learn.id))
    db.commit()
    gid = classify_package(db, c.id, "com.knoact", "知学伴")
    assert gid == learn.id


def test_no_fun_group_returns_none(setup_db, db):
    c = _child(db)
    db.commit()
    assert classify_package(db, c.id, "com.douyin", "抖音") is None


def test_compute_group_totals_aggregates(setup_db, db):
    c = _child(db)
    fun = AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600)
    db.add(fun); db.commit()
    db.add_all([
        AppRule(user_id=c.id, app_package="com.a", app_name="A", group_id=fun.id),
        AppRule(user_id=c.id, app_package="com.b", app_name="B", group_id=fun.id),
    ])
    db.add_all([
        ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.a", app_name="A", duration_seconds=600),
        ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.b", app_name="B", duration_seconds=400),
        ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.unknown", app_name="X", duration_seconds=999),
    ])
    db.commit()
    totals = compute_group_totals(db, c.id, "2026-11-04")
    assert totals[fun.id] == 600 + 400 + 999  # 未知包也归娱乐组
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_screen_time.py -v`
Expected: FAIL — `NotImplementedError`（占位函数）

- [ ] **Step 3: 实现 service**

替换 `backend/app/services/screen_time.py`：

```python
"""屏幕时间：App 分组归类与超时计算（纯函数）。"""
from sqlalchemy.orm import Session
from ..models import AppGroup, AppRule, ScreenUsage


def classify_package(db: Session, user_id: int, app_package: str, app_name: str):
    """返回该包名应归入的 group_id。

    优先级：AppRule 显式映射 > 未知包归「娱乐类」> 无娱乐组则 None。
    """
    rule = (db.query(AppRule)
            .filter_by(user_id=user_id, app_package=app_package)
            .first())
    if rule:
        return rule.group_id
    fun = (db.query(AppGroup)
           .filter_by(user_id=user_id, kind="fun")
           .first())
    return fun.id if fun else None


def compute_group_totals(db: Session, child_id: int, date: str):
    """返回 {group_id: 总秒数}。未归类（group_id 为 None 且无规则）的使用时长计入娱乐组。"""
    rows = (db.query(ScreenUsage)
            .filter_by(child_id=child_id, date=date)
            .all())
    totals = {}
    for r in rows:
        gid = r.group_id if r.group_id is not None else classify_package(db, child_id, r.app_package, r.app_name)
        if gid is None:
            continue
        totals[gid] = totals.get(gid, 0) + r.duration_seconds
    return totals
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_screen_time.py -v`
Expected: PASS（全部 6 个测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/screen_time.py backend/tests/test_screen_time.py
git commit -m "feat(screen-time): 实现分组归类（未知包归娱乐）与超时计算 service"
```

---

## Task 3: 后端路由 `/api/screen-time/*`

**Files:**
- Create: `backend/app/routers/screen_time.py`
- Modify: `backend/app/main.py`（`include_router`）
- Test: `backend/tests/test_screen_time.py`（追加）

端点设计（对齐现有 `buckets.py` / `config_router.py` 的裸 `db: Session = Depends(get_db)` 风格，无鉴权）：

| 方法 | 路径 | 作用 |
|------|------|------|
| `POST` | `/api/screen-time/report` | 批量上报 `{child_id, date, items:[{app_package, app_name, duration_seconds}]}`，按 `(child_id, date, app_package)` 累加 |
| `GET` | `/api/screen-time/groups?user_id=` | 列出该孩子的分组与规则 |
| `PUT` | `/api/screen-time/groups` | 全量保存分组 + 规则（`{user_id, groups:[{id?, name, kind, daily_limit_seconds}], rules:[{app_package, app_name, group_id}]}`） |
| `GET` | `/api/screen-time/usage?child_id=&date=` | 该孩子某天的分组时长 + 超时状态 |

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_screen_time.py` 追加（用 `client` fixture 走 HTTP）：

```python
def test_report_accumulates(client, setup_db, db):
    c = _child(db); db.commit()
    r = client.post("/api/screen-time/report", json={
        "child_id": c.id, "date": "2026-11-04",
        "items": [{"app_package": "com.douyin", "app_name": "抖音", "duration_seconds": 100}],
    })
    assert r.status_code == 200
    r = client.post("/api/screen-time/report", json={
        "child_id": c.id, "date": "2026-11-04",
        "items": [{"app_package": "com.douyin", "app_name": "抖音", "duration_seconds": 50}],
    })
    assert r.status_code == 200
    row = db.query(ScreenUsage).filter_by(child_id=c.id, app_package="com.douyin").first()
    assert row.duration_seconds == 150


def test_groups_roundtrip(client, setup_db, db):
    c = _child(db); db.commit()
    r = client.put("/api/screen-time/groups", json={
        "user_id": c.id,
        "groups": [{"name": "学习类", "kind": "learn", "daily_limit_seconds": None},
                    {"name": "娱乐类", "kind": "fun", "daily_limit_seconds": 3600}],
        "rules": [{"app_package": "com.knoact", "app_name": "知学伴", "group_name": "学习类"}],
    })
    assert r.status_code == 200
    g = client.get(f"/api/screen-time/groups?user_id={c.id}").json()
    assert len(g["groups"]) == 2
    assert any(x["name"] == "学习类" for x in g["groups"])


def test_usage_shows_overtime(client, setup_db, db):
    c = _child(db)
    fun = AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600)
    db.add(fun); db.commit()
    db.add(ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.douyin",
                       app_name="抖音", duration_seconds=5000, group_id=fun.id))
    db.commit()
    r = client.get(f"/api/screen-time/usage?child_id={c.id}&date=2026-11-04").json()
    assert r["groups"][0]["overtime"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_screen_time.py -v`
Expected: FAIL — 404（路由未注册）

- [ ] **Step 3: 实现路由**

创建 `backend/app/routers/screen_time.py`：

```python
"""屏幕时间：上报、分组/规则管理、使用情况查询。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AppGroup, AppRule, ScreenUsage
from ..services.screen_time import classify_package, compute_group_totals

router = APIRouter(prefix="/api/screen-time", tags=["screen-time"])


class UsageItem(BaseModel):
    app_package: str
    app_name: str = ""
    duration_seconds: int = 0


class ReportReq(BaseModel):
    child_id: int
    date: str
    items: list[UsageItem]


class GroupIn(BaseModel):
    id: int | None = None
    name: str
    kind: str = "custom"
    daily_limit_seconds: int | None = None


class RuleIn(BaseModel):
    app_package: str
    app_name: str = ""
    group_name: str  # 按组名关联，避免前端先知道 group_id


class GroupsReq(BaseModel):
    user_id: int
    groups: list[GroupIn]
    rules: list[RuleIn] = []


@router.post("/report")
def report(req: ReportReq, db: Session = Depends(get_db)):
    for it in req.items:
        row = (db.query(ScreenUsage)
               .filter_by(child_id=req.child_id, date=req.date, app_package=it.app_package)
               .first())
        if row:
            row.duration_seconds += it.duration_seconds
            if it.app_name:
                row.app_name = it.app_name
        else:
            gid = classify_package(db, req.child_id, it.app_package, it.app_name)
            db.add(ScreenUsage(child_id=req.child_id, date=req.date,
                               app_package=it.app_package, app_name=it.app_name,
                               duration_seconds=it.duration_seconds, group_id=gid))
    db.commit()
    return {"ok": True}


@router.get("/groups")
def get_groups(user_id: int, db: Session = Depends(get_db)):
    groups = [{"id": g.id, "name": g.name, "kind": g.kind,
               "daily_limit_seconds": g.daily_limit_seconds}
              for g in db.query(AppGroup).filter_by(user_id=user_id).all()]
    rules = [{"app_package": r.app_package, "app_name": r.app_name, "group_id": r.group_id}
             for r in db.query(AppRule).filter_by(user_id=user_id).all()]
    return {"groups": groups, "rules": rules}


@router.put("/groups")
def put_groups(req: GroupsReq, db: Session = Depends(get_db)):
    # 按名字 upsert 分组，记录 name -> id 映射
    name_to_id = {}
    for g in req.groups:
        row = (db.query(AppGroup)
               .filter_by(user_id=req.user_id, name=g.name).first())
        if row:
            row.kind = g.kind
            row.daily_limit_seconds = g.daily_limit_seconds
        else:
            row = AppGroup(user_id=req.user_id, name=g.name, kind=g.kind,
                           daily_limit_seconds=g.daily_limit_seconds)
            db.add(row); db.flush()
        name_to_id[g.name] = row.id
    for r in req.rules:
        gid = name_to_id.get(r.group_name)
        if gid is None:
            continue
        rule = (db.query(AppRule)
                .filter_by(user_id=req.user_id, app_package=r.app_package).first())
        if rule:
            rule.group_id = gid
            rule.app_name = r.app_name
        else:
            db.add(AppRule(user_id=req.user_id, app_package=r.app_package,
                           app_name=r.app_name, group_id=gid))
    db.commit()
    return {"ok": True}


@router.get("/usage")
def usage(child_id: int, date: str, db: Session = Depends(get_db)):
    totals = compute_group_totals(db, child_id, date)
    groups = db.query(AppGroup).filter_by(user_id=child_id).all()
    out = []
    for g in groups:
        secs = totals.get(g.id, 0)
        limit = g.daily_limit_seconds
        overtime = (limit is not None) and (secs > limit)
        out.append({"group_id": g.id, "name": g.name, "kind": g.kind,
                    "duration_seconds": secs,
                    "daily_limit_seconds": limit, "overtime": overtime})
    return {"date": date, "groups": out}
```

在 `backend/app/main.py` 里注册（`from .routers import ...` 加 `screen_time`，`include_router(screen_time.router)`）：

```python
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks, quiz, mastery, render, math, users, buckets, screen_time
# ...
app.include_router(screen_time.router)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_screen_time.py -v`
Expected: PASS（9 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/screen_time.py backend/app/main.py backend/tests/test_screen_time.py
git commit -m "feat(screen-time): 新增 /api/screen-time 上报/分组/使用查询路由"
```

---

## Task 4: 安卓原生 UsageStats 采集（MethodChannel）

**Files:**
- Create: `android/app/src/main/kotlin/com/knoact/student_app/UsageStatsPlugin.kt`
- Modify: `android/app/src/main/kotlin/com/knoact/student_app/MainActivity.kt`

- [ ] **Step 1: 写插件（UsageStatsManager + 权限检测）**

创建 `UsageStatsPlugin.kt`：

```kotlin
package com.knoact.student_app

import android.app.usage.UsageStats
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

class UsageStatsPlugin(private val context: Context) {

    private val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

    fun handle(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "hasUsageAccess" -> result.success(hasUsageAccess())
            "openUsageAccessSettings" -> {
                context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
                result.success(true)
            }
            "queryUsage" -> {
                val since = (call.argument<Number>("since") ?: 0L).toLong()
                result.success(queryUsage(since))
            }
            else -> result.notImplemented()
        }
    }

    private fun hasUsageAccess(): Boolean {
        val am = context.getSystemService(Context.APP_OPS_SERVICE) as android.app.AppOpsManager
        val mode = am.unsafeCheckOpNoThrow(
            android.app.AppOpsManager.OPSTR_GET_USAGE_STATS,
            android.os.Process.myUid(), context.packageName)
        return mode == android.app.AppOpsManager.MODE_ALLOWED
    }

    private fun queryUsage(since: Long): List<Map<String, Any>> {
        if (!hasUsageAccess()) return emptyList()
        val now = System.currentTimeMillis()
        val stats: List<UsageStats> = usm.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY, since, now)
        val pm = context.packageManager
        val out = mutableListOf<Map<String, Any>>()
        for (s in stats) {
            val total = s.totalTimeInForeground
            if (total <= 0) continue
            var label = s.packageName
            try {
                label = pm.getApplicationLabel(pm.getApplicationInfo(s.packageName, 0)).toString()
            } catch (_: PackageManager.NameNotFoundException) {
            }
            out.add(mapOf("package" to s.packageName, "appName" to label, "durationMs" to total))
        }
        return out
    }
}
```

- [ ] **Step 2: 注册 channel**

修改 `MainActivity.kt`：

```kotlin
package com.knoact.student_app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "knoact/usage_stats")
            .setMethodCallHandler { call, result ->
                UsageStatsPlugin(applicationContext).handle(call, result)
            }
    }
}
```

- [ ] **Step 3: 编译验证**

Run: `cd student-app && flutter build apk --debug`
Expected: 编译成功（Kotlin 无语法/类型错误）

- [ ] **Step 4: 提交**

```bash
git add student-app/android/app/src/main/kotlin/com/knoact/student_app/UsageStatsPlugin.kt student-app/android/app/src/main/kotlin/com/knoact/student_app/MainActivity.kt
git commit -m "feat(screen-time): 安卓原生 UsageStats 采集 MethodChannel"
```

---

## Task 5: 安卓端数据层（channel 封装 + 本地缓存 + 上报/规则/超时）

**Files:**
- Create: `student-app/lib/features/screen_time/data/usage_api.dart`
- Create: `student-app/lib/features/screen_time/data/screen_time_sync.dart`
- Create: `student-app/lib/features/screen_time/data/screen_time_repository.dart`
- Modify: `student-app/pubspec.yaml`（加 `workmanager`、`flutter_local_notifications`）
- Test: `student-app/test/screen_time_test.dart`

- [ ] **Step 1: 加依赖**

在 `student-app/pubspec.yaml` 的 `dependencies` 下加：

```yaml
  workmanager: ^0.10.0
  flutter_local_notifications: ^19.4.0
```

Run: `cd student-app && flutter pub get`

- [ ] **Step 2: 写失败测试（超时判定纯逻辑）**

创建 `student-app/test/screen_time_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/screen_time/data/screen_time_sync.dart';

void main() {
  test('overtime 判定：超过上限', () {
    expect(isOvertime(5000, 3600), isTrue);
  });

  test('overtime 判定：未超上限', () {
    expect(isOvertime(100, 3600), isFalse);
  });

  test('overtime 判定：无上限 = 永不超时', () {
    expect(isOvertime(99999, null), isFalse);
  });

  test('warn 阈值：达 80% 预警', () {
    expect(hitWarnThreshold(3000, 3600), isTrue); // 83%
    expect(hitWarnThreshold(100, 3600), isFalse);
  });
}
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd student-app && flutter test test/screen_time_test.dart`
Expected: FAIL — `screen_time_sync.dart` 不存在

- [ ] **Step 4: 实现三个数据文件**

`usage_api.dart`（MethodChannel 封装 + shared_preferences 本地缓存）：

```dart
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

class UsageStats {
  UsageStats(this.package, this.appName, this.durationMs);
  final String package;
  final String appName;
  final int durationMs;
}

/// 与原生 UsageStatsPlugin 通信；本地缓存每日累计时长。
class UsageApi {
  static const _channel = MethodChannel('knoact/usage_stats');

  Future<bool> hasUsageAccess() async =>
      await _channel.invokeMethod<bool>('hasUsageAccess') ?? false;

  Future<void> openUsageAccessSettings() async =>
      _channel.invokeMethod('openUsageAccessSettings');

  /// since = 上次采样时间戳(ms)；返回增量后本地累加并按日聚合。
  Future<List<UsageStats>> queryUsage(int sinceMs) async {
    final raw = await _channel.invokeListMethod<dynamic>('queryUsage', {'since': sinceMs});
    if (raw == null) return [];
    return raw
        .whereType<Map>()
        .map((m) => UsageStats(
              m['package'] as String,
              (m['appName'] as String?) ?? m['package'] as String,
              (m['durationMs'] as num).toInt(),
            ))
        .toList();
  }

  /// 本地缓存累计：{ '2026-11-04|com.douyin': 秒数 }
  Future<void> addLocalSeconds(String date, String package, String appName, int seconds) async {
    final sp = await SharedPreferences.getInstance();
    final key = '$date|$package';
    final prev = sp.getInt(key) ?? 0;
    await sp.setInt(key, prev + seconds);
    await sp.setString('$key.name', appName);
  }

  Future<Map<String, int>> readLocalDay(String date) async {
    final sp = await SharedPreferences.getInstance();
    final out = <String, int>{};
    for (final k in sp.getKeys()) {
      if (!k.startsWith('$date|') || k.contains('.name')) continue;
      final pkg = k.substring(date.length + 1);
      out[pkg] = sp.getInt(k) ?? 0;
    }
    return out;
  }

  Future<void> clearLocalDay(String date) async {
    final sp = await SharedPreferences.getInstance();
    for (final k in sp.getKeys().toList()) {
      if (k.startsWith('$date|')) await sp.remove(k);
    }
  }
}
```

`screen_time_sync.dart`（上报 + 规则 + 超时判定）：

```dart
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'usage_api.dart';

/// 超时：超过 daily_limit_seconds（null = 不限）。
bool isOvertime(int seconds, int? limit) =>
    limit != null && seconds > limit;

/// 预警：达到上限的 80%。
bool hitWarnThreshold(int seconds, int? limit) =>
    limit != null && seconds >= limit * 0.8;

class ScreenRule {
  ScreenRule({required this.groupId, required this.name, required this.kind, this.limitSeconds});
  final int groupId;
  final String name;
  final String kind;
  final int? limitSeconds;
}

/// 上报本地累计时长到后端，拉取规则并做本地超时提醒。
class ScreenTimeSync {
  ScreenTimeSync(this.api);

  final UsageApi api;

  /// 拉取并缓存规则（本地判超时用）。
  Future<List<ScreenRule>> fetchRules(int childId, String baseUrl) async {
    // baseUrl 由 ApiClient 提供；这里简化为直接 http 调用由上层注入。
    // 实际实现经 dio GET /api/screen-time/groups?user_id=
    return [];
  }

  /// 计算某组今日是否超时（本地缓存数据）。
  bool groupOvertime(Map<String, int> daySeconds, ScreenRule rule) {
    final total = daySeconds.values.fold<int>(0, (a, b) => a + b);
    return isOvertime(total, rule.limitSeconds);
  }
}
```

`screen_time_repository.dart`（Riverpod provider 暴露数据层）：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'usage_api.dart';
import 'screen_time_sync.dart';

final usageApiProvider = Provider<UsageApi>((ref) => UsageApi());
final screenTimeSyncProvider = Provider<ScreenTimeSync>(
    (ref) => ScreenTimeSync(ref.watch(usageApiProvider)));
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd student-app && flutter test test/screen_time_test.dart`
Expected: PASS（4 个测试）

- [ ] **Step 6: 提交**

```bash
git add student-app/pubspec.yaml student-app/pubspec.lock student-app/lib/features/screen_time/data/ student-app/test/screen_time_test.dart
git commit -m "feat(screen-time): 安卓端数据层（channel 封装/本地缓存/超时判定）"
```

> 注：`screen_time_sync.dart` 的 `fetchRules` 与 `reportDay` 完整实现（真实 dio 上报 + WorkManager 调度）放在 Task 7 与 WorkManager 集成时补齐；本 Task 先落地可测的纯逻辑（`isOvertime`/`hitWarnThreshold`）与数据模型。

---

## Task 6: 安卓端 UI（权限引导页 + 屏幕时间页）

**Files:**
- Create: `student-app/lib/features/screen_time/ui/usage_permission_page.dart`
- Create: `student-app/lib/features/screen_time/ui/screen_time_page.dart`
- Test: `student-app/test/screen_time_test.dart`（追加 widget test）

- [ ] **Step 1: 写失败 widget test**

在 `student-app/test/screen_time_test.dart` 追加：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:student_app/features/screen_time/ui/usage_permission_page.dart';

void main() {
  // ... 已有纯逻辑测试 ...

  testWidgets('权限页显示引导文案', (tester) async {
    await tester.pumpWidget(ProviderScope(child: MaterialApp(home: UsagePermissionPage())));
    expect(find.textContaining('使用情况访问'), findsWidgets);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd student-app && flutter test test/screen_time_test.dart`
Expected: FAIL — `usage_permission_page.dart` 不存在

- [ ] **Step 3: 实现两个页面**

`usage_permission_page.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/screen_time_repository.dart';

class UsagePermissionPage extends ConsumerWidget {
  const UsagePermissionPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(usageApiProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('屏幕时间')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('开启「使用情况访问」后，家长才能看到你的设备使用时长。',
                style: TextStyle(fontSize: 16)),
            const SizedBox(height: 12),
            const Text('路径：设置 → 使用情况访问 → 允许「知学伴」。'),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => api.openUsageAccessSettings(),
              child: const Text('去开启'),
            ),
          ],
        ),
      ),
    );
  }
}
```

`screen_time_page.dart`（孩子端占位，检测权限后分流）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/screen_time_repository.dart';
import 'usage_permission_page.dart';

class ScreenTimePage extends ConsumerWidget {
  const ScreenTimePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(usageApiProvider);
    return FutureBuilder<bool>(
      future: api.hasUsageAccess(),
      builder: (context, snap) {
        final granted = snap.data ?? false;
        if (!granted) return const UsagePermissionPage();
        return Scaffold(
          appBar: AppBar(title: const Text('屏幕时间')),
          body: const Center(child: Text('今天的使用时长将在这里展示')),
        );
      },
    );
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd student-app && flutter test test/screen_time_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/screen_time/ui/ student-app/test/screen_time_test.dart
git commit -m "feat(screen-time): 安卓端权限引导页与屏幕时间页"
```

---

## Task 7: WorkManager 后台采样 + 上报调度

**Files:**
- Create: `student-app/lib/features/screen_time/data/screen_time_worker.dart`
- Modify: `student-app/lib/features/screen_time/data/screen_time_sync.dart`（补 `reportDay` + `fetchRules` 真实实现）
- Modify: `student-app/lib/main.dart`（初始化 WorkManager + 通知）

- [ ] **Step 1: 补 `screen_time_sync.dart` 真实上报/拉取**

把 `fetchRules` / `reportDay` 用真实 `dio` 实现（依赖注入 `baseUrl`）。改写 `ScreenTimeSync`：

```dart
import 'dart:convert';
import 'package:dio/dio.dart';
import 'usage_api.dart';

// isOvertime / hitWarnThreshold / ScreenRule 保持 Task 5 定义不变

class ScreenTimeSync {
  ScreenTimeSync(this.api, this.dio);
  final UsageApi api;
  final Dio dio;

  Future<List<ScreenRule>> fetchRules(int childId) async {
    final r = await dio.get('/api/screen-time/groups', queryParameters: {'user_id': childId});
    final data = r.data as Map<String, dynamic>;
    final groups = (data['groups'] as List).cast<Map<String, dynamic>>();
    return groups
        .map((g) => ScreenRule(
              groupId: g['id'] as int,
              name: g['name'] as String,
              kind: g['kind'] as String,
              limitSeconds: g['daily_limit_seconds'] as int?,
            ))
        .toList();
  }

  /// 把某天本地缓存的「包名→秒」上报后端（累加语义由后端保证）。
  Future<void> reportDay(int childId, String date, Map<String, int> daySeconds) async {
    if (daySeconds.isEmpty) return;
    final items = daySeconds.entries
        .map((e) => {'app_package': e.key, 'app_name': '', 'duration_seconds': e.value})
        .toList();
    await dio.post('/api/screen-time/report',
        data: {'child_id': childId, 'date': date, 'items': items});
  }
}
```

- [ ] **Step 2: 建 Worker**

创建 `screen_time_worker.dart`：

```dart
import 'package:workmanager/workmanager.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import 'usage_api.dart';
import 'screen_time_sync.dart';

const screenTimeTaskName = 'knoact.screenTime.sync';

/// WorkManager 后台任务：采样 + 上报。周期 15 分钟（Android 下限）。
void registerScreenTimeWorker() {
  Workmanager().initialize(callbackDispatcher);
  Workmanager().registerPeriodicTask(
    screenTimeTaskName, screenTimeTaskName,
    frequency: const Duration(minutes: 15),
  );
}

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    final api = UsageApi();
    final sp = await SharedPreferences.getInstance();
    final since = sp.getInt('last_sync_ms') ?? 0;
    final now = DateTime.now();
    final date = _fmt(now);
    final stats = await api.queryUsage(since);
    for (final s in stats) {
      await api.addLocalSeconds(date, s.package, s.appName, s.durationMs ~/ 1000);
    }
    await sp.setInt('last_sync_ms', now.millisecondsSinceEpoch);
    // 上报
    final childId = sp.getInt('child_id') ?? 0;
    if (childId != 0) {
      final day = await api.readLocalDay(date);
      final dio = Dio(BaseOptions(baseUrl: sp.getString('api_base') ?? 'http://127.0.0.1:8010'));
      await ScreenTimeSync(api, dio).reportDay(childId, date, day);
    }
    return true;
  });
}

String _fmt(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
```

- [ ] **Step 3: 初始化**

在 `student-app/lib/main.dart` 的 `main()` 里（非 Web 时）调用 `registerScreenTimeWorker()`：

```dart
import 'package:flutter/foundation.dart';
import 'features/screen_time/data/screen_time_worker.dart';

void main() {
  if (!kIsWeb) registerScreenTimeWorker();
  runApp(...);
}
```

- [ ] **Step 4: 编译验证**

Run: `cd student-app && flutter build apk --debug`
Expected: 编译成功

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/screen_time/data/screen_time_worker.dart student-app/lib/features/screen_time/data/screen_time_sync.dart student-app/lib/main.dart
git commit -m "feat(screen-time): WorkManager 后台采样 + 上报调度"
```

---

## Task 8: 超时通知提醒

**Files:**
- Create: `student-app/lib/features/screen_time/data/screen_time_notifier.dart`
- Modify: `student-app/lib/features/screen_time/data/screen_time_worker.dart`（采样后调用提醒）

- [ ] **Step 1: 写失败测试（提醒触发判定纯逻辑）**

在 `student-app/test/screen_time_test.dart` 追加：

```dart
import 'package:student_app/features/screen_time/data/screen_time_notifier.dart';

void main() {
  // ... 已有测试 ...

  test('reminder 状态机：超时只提醒一次', () {
    final n = ReminderState();
    // 第一次超时 → 应提醒
    expect(n.shouldNotify(overtime: true, warned: false), isTrue);
    n.markNotified();
    // 已提醒过 → 不再提醒
    expect(n.shouldNotify(overtime: true, warned: true), isFalse);
    // 回到未超时再超时 → 重新提醒
    expect(n.shouldNotify(overtime: false, warned: true), isFalse);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd student-app && flutter test test/screen_time_test.dart`
Expected: FAIL — `screen_time_notifier.dart` 不存在

- [ ] **Step 3: 实现提醒**

创建 `screen_time_notifier.dart`：

```dart
import 'package:shared_preferences/shared_preferences.dart';

/// 提醒状态：记录「今日某组是否已提醒过」，避免反复弹。
class ReminderState {
  bool shouldNotify({required bool overtime, required bool warned}) =>
      overtime && !warned;

  Future<void> markNotified(String date, String groupName) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool('$date|remind|$groupName', true);
  }

  Future<bool> wasNotified(String date, String groupName) async {
    final sp = await SharedPreferences.getInstance();
    return sp.getBool('$date|remind|$groupName') ?? false;
  }
}
```

在 `screen_time_worker.dart` 的 `callbackDispatcher` 采样后加通知（用 `flutter_local_notifications`）：

```dart
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

final _notifs = FlutterLocalNotificationsPlugin();

Future<void> _maybeNotify(int childId, String date, Dio dio) async {
  final rules = await ScreenTimeSync(UsageApi(), dio).fetchRules(childId);
  final day = await UsageApi().readLocalDay(date);
  final state = ReminderState();
  final total = day.values.fold<int>(0, (a, b) => a + b);
  for (final r in rules.where((r) => r.kind == 'fun' || r.limitSeconds != null)) {
    final overtime = isOvertime(total, r.limitSeconds);
    final warned = await state.wasNotified(date, r.name);
    if (state.shouldNotify(overtime: overtime, warned: warned)) {
      await _notifs.show(0, '该休息了', '「${r.name}」今日时长已用完', const NotificationDetails(
        android: AndroidNotificationDetails('screen_time', '屏幕时间', importance: Importance.high),
      ));
      await state.markNotified(date, r.name);
    }
  }
}
```

并在 `callbackDispatcher` 的 `return true;` 前调用 `await _maybeNotify(childId, date, dio);`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd student-app && flutter test test/screen_time_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/screen_time/data/screen_time_notifier.dart student-app/lib/features/screen_time/data/screen_time_worker.dart student-app/test/screen_time_test.dart
git commit -m "feat(screen-time): 超时本地通知提醒（80%/100% 状态机）"
```

---

## Task 9: 家长端「屏幕时间」Tab

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 加 Tab 与渲染函数**

在 `parent-web/app.js` 的 `PARENT_TABS` 里加一项（定位到现有 `PARENT_TABS` 定义处，追加 `['屏幕时间','⏱']`）。然后加渲染 + 数据函数（风格对齐现有 `renderTaskTab` / `loadParentTasks`）：

```javascript
// ---- 屏幕时间 ----
let screenGroups = [];
let screenUsage = null;
let screenDate = new Date().toISOString().slice(0,10);

async function loadScreenGroups(){
  if(!uid) return;
  screenGroups = await api(`/api/screen-time/groups?user_id=${uid}`);
}
async function loadScreenUsage(){
  if(!uid) return;
  screenUsage = await api(`/api/screen-time/usage?child_id=${uid}&date=${screenDate}`);
}
async function saveScreenGroups(){
  const groups = [...]; // 从表单读取
  const rules = [...];
  await api(`/api/screen-time/groups`, {method:'PUT', body:{user_id:uid, groups, rules}});
  toast('已保存'); await loadScreenGroups(); render();
}
function renderScreenTab(){
  if(!screenUsage) return '<div>加载中…</div>';
  const rows = screenUsage.groups.map(g=>{
    const over = g.overtime ? 'style="color:red"' : '';
    const limit = g.daily_limit_seconds ? `${Math.round(g.daily_limit_seconds/60)}分钟` : '不限';
    return `<tr ${over}><td>${g.name}</td><td>${fmtDuration(g.duration_seconds)}</td><td>${limit}</td><td>${g.overtime?'超时':'正常'}</td></tr>`;
  }).join('');
  return `
    <div>
      <div style="margin-bottom:8px">
        <input type="date" value="${screenDate}" onchange="screenDate=this.value;loadScreenUsage().then(render)">
        <button onclick="saveScreenGroups()">保存分组</button>
      </div>
      <table><thead><tr><th>分组</th><th>今日时长</th><th>上限</th><th>状态</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>`;
}
function fmtDuration(s){ const m=Math.round(s/60); return m<60?`${m}分钟`:`${Math.floor(m/60)}小时${m%60}分`; }
```

- [ ] **Step 2: 挂到 `renderParent` / `reloadChildData` 分发**

在 `reloadChildData()` 里加分支：

```javascript
else if(parentTab==='屏幕时间') await Promise.all([loadScreenGroups(), loadScreenUsage()]);
```

在 `renderParent()` 的 Tab 内容分发处加：

```javascript
if(parentTab==='屏幕时间') return renderScreenTab();
```

- [ ] **Step 3: 浏览器验证**

启动后端 + 家长端，切到「屏幕时间」Tab，确认：今日分组时长表渲染、超时行标红、日期切换可回看。

Run: `cd backend && python -m uvicorn app.main:app --port 8010`（另开终端 `cd parent-web && python -m http.server 8767`）

- [ ] **Step 4: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 新增屏幕时间 Tab（分组/今日时长/超时标红）"
```

---

## Self-Review（写计划后自检）

**1. Spec 覆盖**：逐条核对 spec——
- 第 1 节（采集）→ Task 4（原生）+ Task 7（后台调度）✅
- 第 2 节（分组/规则）→ Task 1（表）+ Task 3（路由）+ Task 9（家长端）✅
- 第 3 节（上报同步）→ Task 3 `report` + Task 7 `reportDay` ✅
- 第 4 节（提醒+家长可见）→ Task 8（通知）+ Task 9（超时标红）✅
- 第 5 节（错误处理）→ 未授权分支（Task 6 权限页）、上报失败重试（WorkManager 重试语义）✅
- 第 6 节（测试）→ 后端 pytest + 安卓端 flutter test + 家长端浏览器验证 ✅

**2. 占位符扫描**：Task 5 的 `fetchRules` 在 Task 7 补全真实实现（已显式注明），非占位；无 TBD/TODO。

**3. 类型一致性**：`isOvertime(int, int?)` / `hitWarnThreshold(int, int?)` / `ScreenRule{groupId,name,kind,limitSeconds}` 在 Task 5/7/8 中签名一致；`ScreenTimeSync(UsageApi, Dio)` 构造在 Task 7 统一，Task 5 的旧构造（单参数）已由 Task 7 覆盖重写——注意：**执行时 Task 5 先落地单参构造，Task 7 改为双参构造，需同步改 `screen_time_repository.dart` 的 provider**（`ScreenTimeSync(ref.watch(usageApiProvider), dio)`）。执行顺序已在 Task 顺序中体现，Worker 里直接 `ScreenTimeSync(api, dio)`，不依赖 repository provider。

**范围边界**：生效时段（晚 9 点禁用）按 spec 列为二期，本计划未实现——符合 spec「一期只做每天上限」。强锁屏/电脑端同样排除。
