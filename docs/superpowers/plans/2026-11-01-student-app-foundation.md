# Flutter 学生端骨架 + 学习首页、学习中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本机装好 Flutter 开发环境，新建 Flutter 学生端 `student-app/`（Web + Android），实现登录、自适应导航、学习首页、学习中心、「我的」，并能以 Docker（nginx）部署 Web 版。

**Architecture:** 按功能分模块（`core/` + `features/{auth,shell,home,center,profile}`），每个功能内 `data/`（接口与模型）+ `logic`（纯函数）+ `ui/`。状态用 Riverpod 3（`Notifier` / `AsyncNotifier` / `Provider`），路由用 go_router（`StatefulShellRoute.indexedStack`），网络用 dio。页面只依赖 provider；repository 可在测试中替换为 fake。

**Tech Stack:** Flutter 3.47.9（Dart 3.13）、flutter_riverpod ^3.4.3、go_router ^18.1.2、dio ^5.11.1、shared_preferences ^2.5.6、audioplayers ^6.8.1、flutter_tts ^4.2.5；nginx、docker-compose。

**Spec:** `docs/superpowers/specs/2026-11-01-student-app-foundation-design.md`

**通用约定（所有任务）：**

- 仓库 `D:\workspace\github\KnoAct`，分支 `feat/student-app-foundation`（Task 1 创建），每个任务结束提交，不推送。Shell 为 PowerShell。
- Flutter 位于 `E:\dev\flutter`，Android SDK 位于 `E:\dev\android-sdk`。命令前确保：
  `$env:Path = "E:\dev\flutter\bin;" + $env:Path; $env:PUB_HOSTED_URL='https://pub.flutter-io.cn'; $env:FLUTTER_STORAGE_BASE_URL='https://storage.flutter-io.cn'; $env:ANDROID_HOME='E:\dev\android-sdk'`
- Flutter 命令在 `student-app/` 目录下执行。测试：`flutter test`；静态检查：`flutter analyze`（必须 `No issues found!`）。
- 提交一律用 `git -C D:\workspace\github\KnoAct ...`（不依赖当前目录）。
- 后端本地运行于 `http://127.0.0.1:8010`（`backend/` 下 `py -m uvicorn app.main:app --port 8010`）。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `student-app/lib/main.dart` | 入口：`ProviderScope` + 根组件 |
| `student-app/lib/app.dart` | 根组件：会话加载中显示启动页，否则 `MaterialApp.router` |
| `student-app/lib/core/config.dart` | 解析后端地址 `resolveApiBase` |
| `student-app/lib/core/api_client.dart` | dio 封装、`ApiException`、JSON 校验助手 |
| `student-app/lib/core/providers.dart` | `apiClientProvider` |
| `student-app/lib/core/theme.dart` | 颜色常量与 `buildTheme()` |
| `student-app/lib/core/router.dart` | `routerProvider`（登录守卫 + 外壳路由） |
| `student-app/lib/core/widgets.dart` | 通用组件：`ErrorCard`、`SectionCard`、`showMessage` |
| `student-app/lib/features/auth/data/auth_repository.dart` | `Child`、`AuthRepository`、`NotAChildException` |
| `student-app/lib/features/auth/data/session_store.dart` | shared_preferences 持久化当前孩子 |
| `student-app/lib/features/auth/session.dart` | `sessionProvider`（`AsyncNotifier<Child?>`） |
| `student-app/lib/features/auth/ui/login_page.dart` | 登录页 |
| `student-app/lib/features/shell/app_shell.dart` | 自适应导航外壳 + Tab 切换联动 |
| `student-app/lib/features/home/data/home_models.dart` | `LessonProgress`、`HomeSnapshot`、`StudyTask` |
| `student-app/lib/features/home/data/home_repository.dart` | 首页接口 |
| `student-app/lib/features/home/home_logic.dart` | 纯函数：进度、分组、按钮动作、类型元信息、问候、日期、古诗 |
| `student-app/lib/features/home/home_controller.dart` | `homeControllerProvider`（`AsyncNotifier<HomeData>`） |
| `student-app/lib/features/home/ui/home_page.dart` | 首页页面 |
| `student-app/lib/features/home/ui/home_sections.dart` | 首页各区块组件 |
| `student-app/lib/features/center/data/center_models.dart` | `CenterMaterial`、`CenterQuestion` |
| `student-app/lib/features/center/data/center_repository.dart` | 学习中心接口 |
| `student-app/lib/features/center/center_logic.dart` | `CenterTab`、`shouldAutoSubmit`、`isCorrectAnswer` |
| `student-app/lib/features/center/center_controller.dart` | `centerControllerProvider`（`Notifier<CenterState>`） |
| `student-app/lib/features/center/speech_player.dart` | `SpeechPlayer`：后端 TTS 音频 / 设备朗读兜底 |
| `student-app/lib/features/center/ui/center_page.dart` | 学习中心页面 |
| `student-app/lib/features/profile/ui/profile_page.dart` | 「我的」 |
| `student-app/test/**` | 单元与组件测试 |
| `student-app/Dockerfile`、`nginx.conf`、`.dockerignore` | Web 部署 |
| `docker-compose.yml`、`.env.example`、`README.md` | 新增 student-app 服务与文档 |

---

### Task 1: 开发环境与分支

**由控制者执行（涉及大文件下载与本机环境变量）。** Flutter SDK 已下载解压到 `E:\dev\flutter`，Android cmdline-tools 已解压到 `E:\dev\android-sdk\cmdline-tools\latest`。

- [ ] **Step 1: 用户级环境变量**

```powershell
[Environment]::SetEnvironmentVariable('PUB_HOSTED_URL','https://pub.flutter-io.cn','User')
[Environment]::SetEnvironmentVariable('FLUTTER_STORAGE_BASE_URL','https://storage.flutter-io.cn','User')
[Environment]::SetEnvironmentVariable('ANDROID_HOME','E:\dev\android-sdk','User')
[Environment]::SetEnvironmentVariable('ANDROID_SDK_ROOT','E:\dev\android-sdk','User')
$p = [Environment]::GetEnvironmentVariable('Path','User')
foreach($d in 'E:\dev\flutter\bin','E:\dev\android-sdk\platform-tools','E:\dev\android-sdk\cmdline-tools\latest\bin'){ if($p -notlike "*$d*"){ $p = "$p;$d" } }
[Environment]::SetEnvironmentVariable('Path',$p,'User')
```

- [ ] **Step 2: Android SDK 组件与许可**（先完成 Step 3 的 JDK 确认，sdkmanager 需要 Java）

```powershell
$env:Path = "E:\dev\flutter\bin;E:\dev\android-sdk\cmdline-tools\latest\bin;E:\dev\android-sdk\platform-tools;" + $env:Path
$env:ANDROID_HOME='E:\dev\android-sdk'
flutter config --android-sdk E:\dev\android-sdk
'y`ny`ny`ny`ny`ny`ny`ny`ny`n' | sdkmanager --licenses
sdkmanager "platform-tools" "emulator" "system-images;android-35;google_apis;x86_64"
```

编译所需的 `platforms;android-*` 与 `build-tools;*` 由首次 `flutter build apk` 的 Gradle 自动下载（许可已接受）。

- [ ] **Step 3: JDK**

`flutter doctor -v` 检查 Android toolchain 的 Java。本机已有 Java 18（AGP 8 需 17+，可用）。若 doctor 报 Java 不兼容，下载 Temurin 17 解压到 `E:\dev\jdk-17` 并 `flutter config --jdk-dir E:\dev\jdk-17`。

- [ ] **Step 4: 模拟器（硬件加速检查）**

```powershell
E:\dev\android-sdk\emulator\emulator.exe -accel-check
'no' | avdmanager create avd -n knoact_api35 -k "system-images;android-35;google_apis;x86_64" -d pixel_6
```

`-accel-check` 未报告 WHPX/HAXM/AEHD 可用时，记录「模拟器不可用」，安卓验收按 spec 兜底（只验证 `flutter build apk --debug` 成功）。

- [ ] **Step 5: 验证**

Run: `flutter doctor -v`
Expected: Flutter、Android toolchain（licenses accepted）、Chrome 三项为 ✓（Visual Studio、Android Studio 缺失可忽略）。

- [ ] **Step 6: 分支**

```bash
git checkout -b feat/student-app-foundation
```

---

### Task 2: 工程骨架、配置与 API 客户端

**Files:**
- Create: `student-app/`（`flutter create`），`lib/core/config.dart`、`lib/core/api_client.dart`、`lib/core/providers.dart`、`lib/core/theme.dart`、`lib/core/widgets.dart`
- Test: `test/core/config_test.dart`、`test/core/api_client_test.dart`
- Delete: `test/widget_test.dart`（模板计数器测试）

- [ ] **Step 1: 创建工程与依赖**（仓库根目录）

```powershell
flutter create --project-name student_app --org com.knoact --platforms web,android student-app
cd student-app
flutter pub add flutter_riverpod:^3.4.3 go_router:^18.1.2 dio:^5.11.1 shared_preferences:^2.5.6 audioplayers:^6.8.1 flutter_tts:^4.2.5
Remove-Item test\widget_test.dart
```

注：`flutter` 为 `.bat`，经 cmd 执行时版本号中的 `^` 会被吞掉，`pubspec.yaml` 中将记录为精确版本（如 `flutter_riverpod: 3.4.3`），属预期。

- [ ] **Step 2: 写失败的测试**

`test/core/config_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/config.dart';

void main() {
  test('未定义 API_BASE 时连本地开发后端', () {
    expect(resolveApiBase(hasDefine: false, defined: '', isWeb: true), 'http://127.0.0.1:8010');
  });
  test('定义了非空 API_BASE 时原样使用', () {
    expect(resolveApiBase(hasDefine: true, defined: 'http://10.0.2.2:8010', isWeb: false), 'http://10.0.2.2:8010');
  });
  test('Web 上 API_BASE 为空串时走同源', () {
    expect(
      resolveApiBase(hasDefine: true, defined: '', isWeb: true, pageUri: Uri.parse('https://kid.example.com:8082/#/home')),
      'https://kid.example.com:8082',
    );
  });
  test('非 Web 上 API_BASE 为空串时回落本地开发后端', () {
    expect(resolveApiBase(hasDefine: true, defined: '', isWeb: false), 'http://127.0.0.1:8010');
  });
}
```

`test/core/api_client_test.dart`：

```dart
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';

class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.status, this.body, this.contentType);
  final int status;
  final List<int> body;
  final String contentType;
  RequestOptions? last;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    last = options;
    return ResponseBody.fromBytes(body, status, headers: {
      Headers.contentTypeHeader: [contentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

ApiClient _client(_FakeAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://api.test'));
  dio.httpClientAdapter = adapter;
  return ApiClient('http://api.test', dio: dio);
}

void main() {
  test('get 返回解析后的 JSON', () async {
    final a = _FakeAdapter(200, utf8.encode('{"balance": 35}'), 'application/json');
    final data = await _client(a).get('/api/points/balance', query: {'user_id': 4});
    expect(data, {'balance': 35});
    expect(a.last!.uri.toString(), 'http://api.test/api/points/balance?user_id=4');
  });

  test('非 2xx 抛出带状态码的 ApiException', () async {
    final a = _FakeAdapter(502, utf8.encode('<html>502 Bad Gateway</html>'), 'text/html');
    expect(
      () => _client(a).get('/api/home/snapshot'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 502)),
    );
  });

  test('getBytes 返回字节与 content-type', () async {
    final a = _FakeAdapter(200, [1, 2, 3], 'audio/mpeg');
    final r = await _client(a).getBytes('/api/tts/synthesize', query: {'text': 'hi'});
    expect(r.bytes, [1, 2, 3]);
    expect(r.contentType, 'audio/mpeg');
  });

  test('asMap / asList 对非预期结构抛 ApiException', () {
    expect(asMap({'a': 1}), {'a': 1});
    expect(asList([1]), [1]);
    expect(() => asMap('<html>'), throwsA(isA<ApiException>()));
    expect(() => asList({'a': 1}), throwsA(isA<ApiException>()));
  });
}
```

- [ ] **Step 3: 运行测试确认失败**

Run: `flutter test test/core`
Expected: 编译失败（`config.dart` / `api_client.dart` 不存在）。

- [ ] **Step 4: 实现**

`lib/core/config.dart`：

```dart
import 'package:flutter/foundation.dart';

const bool _hasApiBase = bool.hasEnvironment('API_BASE');
const String _apiBase = String.fromEnvironment('API_BASE');
const String localApiBase = 'http://127.0.0.1:8010';

/// 后端地址：未定义 API_BASE 时连本地开发后端；定义为空串时 Web 走同源（经 nginx 反代）。
String resolveApiBase({
  bool hasDefine = _hasApiBase,
  String defined = _apiBase,
  bool isWeb = kIsWeb,
  Uri? pageUri,
}) {
  if (!hasDefine) return localApiBase;
  if (defined.isNotEmpty) return defined;
  if (isWeb) return (pageUri ?? Uri.base).origin;
  return localApiBase;
}
```

`lib/core/api_client.dart`：

```dart
import 'package:dio/dio.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

Map<String, dynamic> asMap(Object? data) {
  if (data is Map) return Map<String, dynamic>.from(data);
  throw ApiException('响应格式错误');
}

List<dynamic> asList(Object? data) {
  if (data is List) return data;
  throw ApiException('响应格式错误');
}

class ApiClient {
  ApiClient(String baseUrl, {Dio? dio})
      : _dio = dio ??
            Dio(BaseOptions(
              baseUrl: baseUrl,
              connectTimeout: const Duration(seconds: 10),
              // 听力/阅读材料与 TTS 可能当场调用大模型生成
              receiveTimeout: const Duration(seconds: 120),
            ));

  final Dio _dio;

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      _send(() => _dio.get<dynamic>(path, queryParameters: query));

  Future<dynamic> post(String path, {Object? body}) => _send(() => _dio.post<dynamic>(path, data: body));

  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) async {
    try {
      final r = await _dio.get<List<int>>(
        path,
        queryParameters: query,
        options: Options(responseType: ResponseType.bytes),
      );
      return (bytes: r.data ?? const <int>[], contentType: r.headers.value(Headers.contentTypeHeader) ?? '');
    } on DioException catch (e) {
      throw _wrap(e);
    }
  }

  Future<dynamic> _send(Future<Response<dynamic>> Function() call) async {
    try {
      return (await call()).data;
    } on DioException catch (e) {
      throw _wrap(e);
    }
  }

  ApiException _wrap(DioException e) =>
      ApiException(e.message ?? e.type.name, statusCode: e.response?.statusCode);
}
```

`lib/core/providers.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'config.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient(resolveApiBase()));
```

`lib/core/theme.dart`：

```dart
import 'package:flutter/material.dart';

/// 配色沿用旧版学生端（frontend/index.html 的 CSS 变量）
class AppColors {
  static const blue = Color(0xFF3158E8);
  static const blueSoft = Color(0xFFEDF1FF);
  static const green = Color(0xFF2E8B5A);
  static const greenSoft = Color(0xFFE8F7EF);
  static const orange = Color(0xFFDC872D);
  static const orangeSoft = Color(0xFFFFF2DF);
  static const gold = Color(0xFFF59D20);
  static const bg = Color(0xFFF7F8F5);
  static const ink = Color(0xFF202723);
  static const gray = Color(0xFF78817B);
  static const line = Color(0xFFE3E7E0);
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: AppColors.blue, primary: AppColors.blue, surface: Colors.white);
  return ThemeData(
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.bg,
    useMaterial3: true,
    cardTheme: const CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(20)),
        side: BorderSide(color: AppColors.line),
      ),
    ),
  );
}
```

`lib/core/widgets.dart`：

```dart
import 'package:flutter/material.dart';

import 'theme.dart';

void showMessage(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text)));
}

class ErrorCard extends StatelessWidget {
  const ErrorCard({super.key, required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.cloud_off, size: 40, color: AppColors.gray),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.gray)),
          const SizedBox(height: 12),
          FilledButton(onPressed: onRetry, child: const Text('重试')),
        ]),
      ),
    );
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(20)});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: padding, child: child));
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `flutter test test/core` → 全部通过。Run: `flutter analyze` → `No issues found!`（`lib/main.dart` 模板此时仍在，不报错即可）。

- [ ] **Step 6: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): Flutter 工程骨架、后端地址配置与 API 客户端"
```

（`flutter create` 生成的 `.gitignore` 已排除 `build/`、`.dart_tool/` 等。）

---

### Task 3: 登录、会话、路由、自适应外壳、「我的」

**Files:**
- Create: `lib/features/auth/data/auth_repository.dart`、`lib/features/auth/data/session_store.dart`、`lib/features/auth/session.dart`、`lib/features/auth/ui/login_page.dart`、`lib/features/shell/app_shell.dart`、`lib/features/profile/ui/profile_page.dart`、`lib/core/router.dart`、`lib/app.dart`
- Modify: `lib/main.dart`（替换模板）
- Test: `test/features/auth/session_test.dart`、`test/features/auth/login_page_test.dart`

本任务中首页、学习中心先用占位页（Task 5、7 替换）：`HomePage` 与 `CenterPage` 暂在各自文件中返回 `Center(child: Text('首页'))` / `Center(child: Text('学习中心'))`，文件路径按最终结构创建：`lib/features/home/ui/home_page.dart`、`lib/features/center/ui/center_page.dart`。「我的」页积分在 Task 5 接入，本任务先显示名字与退出按钮。

- [ ] **Step 1: 写失败的测试**

`test/features/auth/session_test.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';

class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository(this.result);
  final Object result; // Child 或 Exception
  String? lastName;

  @override
  Future<Child> login(String name) async {
    lastName = name;
    if (result is Child) return result as Child;
    throw result;
  }
}

ProviderContainer makeContainer(AuthRepository repo) {
  final c = ProviderContainer(
    overrides: [authRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(c.dispose);
  return c;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('未登录时会话为 null', () async {
    final c = makeContainer(FakeAuthRepository(const Child(4, '金同学')));
    expect(await c.read(sessionProvider.future), isNull);
  });

  test('登录成功后保存并可在重建后恢复', () async {
    final repo = FakeAuthRepository(const Child(4, '金同学'));
    final c = makeContainer(repo);
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('  金同学 ');
    expect(repo.lastName, '金同学');
    expect(c.read(sessionProvider).value, const Child(4, '金同学'));

    final c2 = makeContainer(repo);
    expect(await c2.read(sessionProvider.future), const Child(4, '金同学'));
  });

  test('登录到非孩子账号时抛 NotAChildException 且不保存', () async {
    final c = makeContainer(FakeAuthRepository(NotAChildException()));
    await c.read(sessionProvider.future);
    await expectLater(c.read(sessionProvider.notifier).login('金爸爸'), throwsA(isA<NotAChildException>()));
    expect(c.read(sessionProvider).value, isNull);
  });

  test('退出登录清除保存', () async {
    final c = makeContainer(FakeAuthRepository(const Child(4, '金同学')));
    await c.read(sessionProvider.future);
    await c.read(sessionProvider.notifier).login('金同学');
    await c.read(sessionProvider.notifier).logout();
    expect(c.read(sessionProvider).value, isNull);
    final c2 = makeContainer(FakeAuthRepository(const Child(4, '金同学')));
    expect(await c2.read(sessionProvider.future), isNull);
  });
}
```

`test/features/auth/login_page_test.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/auth/ui/login_page.dart';

import 'session_test.dart' show FakeAuthRepository;

Future<ProviderContainer> pumpLogin(WidgetTester tester, AuthRepository repo) async {
  final container = ProviderContainer(
    overrides: [authRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: LoginPage()),
  ));
  await tester.pumpAndSettle();
  return container;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('名字为空时登录按钮不可用', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(const Child(4, '金同学')));
    final button = tester.widget<FilledButton>(find.widgetWithText(FilledButton, '开始学习'));
    expect(button.onPressed, isNull);
    expect(find.text('首次使用会自动创建账号，请确认名字无误'), findsOneWidget);
  });

  testWidgets('输入名字登录成功后会话有值', (tester) async {
    final c = await pumpLogin(tester, FakeAuthRepository(const Child(4, '金同学')));
    await tester.enterText(find.byType(TextField), '金同学');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
    await tester.pumpAndSettle();
    expect(c.read(sessionProvider).value, const Child(4, '金同学'));
  });

  testWidgets('家长名字提示不是孩子账号', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(NotAChildException()));
    await tester.enterText(find.byType(TextField), '金爸爸');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
    await tester.pumpAndSettle();
    expect(find.text('这个名字不是孩子账号，请输入孩子的名字'), findsOneWidget);
  });

  testWidgets('接口失败提示检查网络', (tester) async {
    await pumpLogin(tester, FakeAuthRepository(ApiException('boom')));
    await tester.enterText(find.byType(TextField), '金同学');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '开始学习'));
    await tester.pumpAndSettle();
    expect(find.text('登录失败，请检查网络或后端服务'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/auth` → 编译失败（文件不存在）。

- [ ] **Step 3: 实现**

`lib/features/auth/data/auth_repository.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

class Child {
  const Child(this.id, this.name);

  final int id;
  final String name;

  @override
  bool operator ==(Object other) => other is Child && other.id == id && other.name == name;

  @override
  int get hashCode => Object.hash(id, name);
}

class NotAChildException implements Exception {}

class AuthRepository {
  AuthRepository(this._api);

  final ApiClient _api;

  /// 按名字登录；后端找不到名字会自动创建孩子账号。返回非孩子账号时抛 [NotAChildException]。
  Future<Child> login(String name) async {
    final d = asMap(await _api.post('/api/auth/login', body: {'name': name}));
    if (d['role'] != 'child') throw NotAChildException();
    return Child((d['id'] as num).toInt(), d['name'] as String);
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) => AuthRepository(ref.watch(apiClientProvider)));
```

`lib/features/auth/data/session_store.dart`：

```dart
import 'package:shared_preferences/shared_preferences.dart';

import 'auth_repository.dart';

class SessionStore {
  static const _kId = 'knoact_child_id';
  static const _kName = 'knoact_child_name';

  Future<Child?> load() async {
    final p = await SharedPreferences.getInstance();
    final id = p.getInt(_kId);
    final name = p.getString(_kName);
    return (id != null && name != null) ? Child(id, name) : null;
  }

  Future<void> save(Child c) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kId, c.id);
    await p.setString(_kName, c.name);
  }

  Future<void> clear() async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_kId);
    await p.remove(_kName);
  }
}
```

`lib/features/auth/session.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'data/auth_repository.dart';
import 'data/session_store.dart';

final sessionStoreProvider = Provider<SessionStore>((ref) => SessionStore());

class SessionNotifier extends AsyncNotifier<Child?> {
  @override
  Future<Child?> build() => ref.read(sessionStoreProvider).load();

  Future<void> login(String name) async {
    final child = await ref.read(authRepositoryProvider).login(name.trim());
    await ref.read(sessionStoreProvider).save(child);
    state = AsyncData(child);
  }

  Future<void> logout() async {
    await ref.read(sessionStoreProvider).clear();
    state = const AsyncData(null);
  }
}

final sessionProvider = AsyncNotifierProvider<SessionNotifier, Child?>(SessionNotifier.new);

/// 已登录孩子的 id；仅在登录后的页面使用。
final currentChildIdProvider = Provider<int>((ref) => ref.watch(sessionProvider).value!.id);
```

`lib/features/auth/ui/login_page.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../data/auth_repository.dart';
import '../session.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _name = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(sessionProvider.notifier).login(_name.text);
    } on NotAChildException {
      _error = '这个名字不是孩子账号，请输入孩子的名字';
    } catch (_) {
      _error = '登录失败，请检查网络或后端服务';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final canSubmit = !_busy && _name.text.trim().isNotEmpty;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Icon(Icons.auto_awesome, size: 48, color: AppColors.blue),
              const SizedBox(height: 12),
              const Text('知学伴', textAlign: TextAlign.center, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
              const Text('你的 AI 学习伙伴', textAlign: TextAlign.center, style: TextStyle(color: AppColors.gray)),
              const SizedBox(height: 28),
              TextField(
                controller: _name,
                decoration: const InputDecoration(labelText: '你的名字', border: OutlineInputBorder()),
                onChanged: (_) => setState(() {}),
                onSubmitted: (_) => canSubmit ? _submit() : null,
              ),
              const SizedBox(height: 8),
              const Text('首次使用会自动创建账号，请确认名字无误', style: TextStyle(fontSize: 12, color: AppColors.gray)),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 20),
              FilledButton(onPressed: canSubmit ? _submit : null, child: const Text('开始学习')),
            ]),
          ),
        ),
      ),
    );
  }
}
```

`lib/features/profile/ui/profile_page.dart`（本任务版本，Task 5 加积分）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/widgets.dart';
import '../../auth/session.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final child = ref.watch(sessionProvider).value;
    return ListView(padding: const EdgeInsets.all(20), children: [
      SectionCard(
        child: Row(children: [
          CircleAvatar(radius: 26, child: Text(child == null ? '' : child.name.characters.last)),
          const SizedBox(width: 16),
          Expanded(child: Text(child?.name ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700))),
        ]),
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () => ref.read(sessionProvider.notifier).logout(),
        icon: const Icon(Icons.logout),
        label: const Text('退出登录'),
      ),
    ]);
  }
}
```

`lib/features/shell/app_shell.dart`（本任务版本：仅导航；Task 5、7 加 Tab 切换联动）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';

const _destinations = [
  (icon: Icons.home_outlined, selected: Icons.home, label: '首页'),
  (icon: Icons.menu_book_outlined, selected: Icons.menu_book, label: '学习中心'),
  (icon: Icons.person_outline, selected: Icons.person, label: '我的'),
];

/// 宽度 >= 840 用左侧 NavigationRail，否则底部 NavigationBar
const double kWideBreakpoint = 840;

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  void _go(int index) =>
      widget.navigationShell.goBranch(index, initialLocation: index == widget.navigationShell.currentIndex);

  @override
  Widget build(BuildContext context) {
    final index = widget.navigationShell.currentIndex;
    return LayoutBuilder(builder: (context, c) {
      if (c.maxWidth >= kWideBreakpoint) {
        return Scaffold(
          body: Row(children: [
            NavigationRail(
              selectedIndex: index,
              onDestinationSelected: _go,
              labelType: NavigationRailLabelType.all,
              leading: const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Text('知学伴', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.blue)),
              ),
              destinations: [
                for (final d in _destinations)
                  NavigationRailDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selected), label: Text(d.label)),
              ],
            ),
            const VerticalDivider(width: 1),
            Expanded(
              child: Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1200), child: widget.navigationShell),
              ),
            ),
          ]),
        );
      }
      return Scaffold(
        body: SafeArea(child: widget.navigationShell),
        bottomNavigationBar: NavigationBar(
          selectedIndex: index,
          onDestinationSelected: _go,
          destinations: [
            for (final d in _destinations)
              NavigationDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selected), label: d.label),
          ],
        ),
      );
    });
  }
}
```

`lib/core/router.dart`：

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/session.dart';
import '../features/auth/ui/login_page.dart';
import '../features/center/ui/center_page.dart';
import '../features/home/ui/home_page.dart';
import '../features/profile/ui/profile_page.dart';
import '../features/shell/app_shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);
  return GoRouter(
    initialLocation: '/home',
    refreshListenable: refresh,
    redirect: (context, state) {
      final loggedIn = ref.read(sessionProvider).value != null;
      final atLogin = state.matchedLocation == '/login';
      if (!loggedIn) return atLogin ? null : '/login';
      return atLogin ? '/home' : null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, _) => const LoginPage()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => AppShell(navigationShell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, _) => const HomePage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/center', builder: (_, _) => const CenterPage())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, _) => const ProfilePage())]),
        ],
      ),
    ],
  );
});
```

`lib/app.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router.dart';
import 'core/theme.dart';
import 'features/auth/session.dart';

class StudentApp extends ConsumerWidget {
  const StudentApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 会话（本地存储）读取完成前不建路由，避免先跳登录页再跳首页
    if (ref.watch(sessionProvider).isLoading) {
      return MaterialApp(
        theme: buildTheme(),
        home: const Scaffold(body: Center(child: CircularProgressIndicator())),
      );
    }
    return MaterialApp.router(
      title: '知学伴',
      theme: buildTheme(),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
```

`lib/main.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  // 关闭 Riverpod 3 的自动重试：加载失败由页面的「重试」按钮处理
  runApp(ProviderScope(retry: (_, _) => null, child: const StudentApp()));
}
```

占位页 `lib/features/home/ui/home_page.dart`：

```dart
import 'package:flutter/material.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) => const Center(child: Text('首页'));
}
```

占位页 `lib/features/center/ui/center_page.dart`：

```dart
import 'package:flutter/material.dart';

class CenterPage extends StatelessWidget {
  const CenterPage({super.key});

  @override
  Widget build(BuildContext context) => const Center(child: Text('学习中心'));
}
```

- [ ] **Step 4: 运行测试与静态检查**

Run: `flutter test` → 全部通过。Run: `flutter analyze` → `No issues found!`

- [ ] **Step 5: 冒烟运行**

后端运行时：`flutter run -d chrome`，输入「金同学」登录 → 进入外壳（占位首页），窄窗口为底部导航、宽窗口为左侧导航；「我的」退出后回到登录页。

- [ ] **Step 6: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): 登录与会话、路由守卫、自适应导航外壳、我的页"
```

---

### Task 4: 首页数据层与纯逻辑

**Files:**
- Create: `lib/features/home/data/home_models.dart`、`lib/features/home/data/home_repository.dart`、`lib/features/home/home_logic.dart`
- Test: `test/features/home/home_models_test.dart`、`test/features/home/home_logic_test.dart`

- [ ] **Step 1: 写失败的测试**

`test/features/home/home_models_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/home/data/home_models.dart';

void main() {
  test('HomeSnapshot 解析快照', () {
    final s = HomeSnapshot.fromJson({
      'user_name': '金同学',
      'points': 35,
      'lesson_progress': {'current': 3, 'total': 8, 'mastered': 2, 'current_lesson_id': 46},
    });
    expect(s.userName, '金同学');
    expect(s.lessonProgress.current, 3);
    expect(s.lessonProgress.total, 8);
    expect(s.lessonProgress.mastered, 2);
    expect(s.lessonProgress.currentLessonId, 46);
  });

  test('HomeSnapshot 缺字段时给默认值', () {
    final s = HomeSnapshot.fromJson({});
    expect(s.userName, '同学');
    expect(s.lessonProgress.current, 1);
    expect(s.lessonProgress.total, 0);
    expect(s.lessonProgress.currentLessonId, isNull);
  });

  test('StudyTask 解析任务', () {
    final t = StudyTask.fromJson({
      'id': 85, 'subject': '语文', 'task_type': 'reading', 'title': '桂花雨 阅读理解',
      'detail': null, 'points': 20, 'submit_status': 'not_started',
    });
    expect(t.id, 85);
    expect(t.subject, '语文');
    expect(t.taskType, 'reading');
    expect(t.detail, '');
    expect(t.points, 20);
    expect(t.submitStatus, 'not_started');
  });
}
```

`test/features/home/home_logic_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/home_logic.dart';

StudyTask task(int id, String subject, String type, String status) => StudyTask(
    id: id, subject: subject, taskType: type, title: 't$id', detail: '', points: 20, submitStatus: status);

void main() {
  final tasks = [
    task(1, '语文', 'dictation', 'approved'),
    task(2, '语文', 'reading', 'not_started'),
    task(3, '英语', 'listening', 'submitted'),
    task(4, '数学', 'math', 'approved'),
    task(5, '', 'custom', 'not_started'),
  ];

  test('今日总进度：approved 才算完成', () {
    final p = dayProgress(tasks);
    expect(p.done, 2);
    expect(p.total, 5);
    expect(p.percent, 40);
    expect(dayProgress([]).percent, 0);
  });

  test('各学科进度', () {
    final m = subjectProgress(tasks);
    expect(m['语文'], (done: 1, total: 2));
    expect(m['英语'], (done: 0, total: 1));
    expect(m['数学'], (done: 1, total: 1));
  });

  test('学科待完成数', () {
    expect(remainingCount(tasks, '语文'), 1);
    expect(remainingCount(tasks, '数学'), 0);
  });

  test('按学科分组：无学科的任务出现在每个学科', () {
    final g = groupForSubject(tasks, '语文');
    expect(g.todo.map((t) => t.id), [2, 5]);
    expect(g.done.map((t) => t.id), [1]);
  });

  test('任务按钮动作', () {
    expect(taskAction(task(1, '语文', 'dictation', 'approved')), TaskAction.done);
    expect(taskAction(task(1, '语文', 'math', 'submitted')), TaskAction.waiting);
    expect(taskAction(task(1, '语文', 'reading', 'not_started')), TaskAction.openReading);
    expect(taskAction(task(1, '英语', 'listening', 'not_started')), TaskAction.openListening);
    for (final type in ['dictation', 'math', 'knowledge', 'review', 'custom']) {
      expect(taskAction(task(1, '语文', type, 'not_started')), TaskAction.comingSoon);
    }
  });

  test('任务类型元信息与旧版一致', () {
    expect(taskMeta('dictation').tag, '当前进度');
    expect(taskMeta('reading').minutes, '约 12 分钟');
    expect(taskMeta('unknown').tag, '自定义');
  });

  test('问候语按时段', () {
    expect(greeting(3), '夜深了');
    expect(greeting(9), '早上好');
    expect(greeting(15), '下午好');
    expect(greeting(20), '晚上好');
  });

  test('日期文案与接口日期', () {
    final d = DateTime(2026, 11, 1);
    expect(dateLabel(d), '11 月 1 日，星期日');
    expect(apiDate(d), '2026-11-01');
  });

  test('古诗按天轮换', () {
    final day0 = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
    expect(todayPoem(day0).name, '竹');
    expect(todayPoem(day0.add(const Duration(days: 1))).name, '兰');
    expect(todayPoem(day0.add(const Duration(days: 4))).name, '竹');
  });
}
```

- [ ] **Step 2: 运行确认失败** — `flutter test test/features/home` → 编译失败。

- [ ] **Step 3: 实现**

`lib/features/home/data/home_models.dart`：

```dart
int _int(Object? v, int fallback) => v is num ? v.toInt() : fallback;

class LessonProgress {
  const LessonProgress({required this.current, required this.total, required this.mastered, this.currentLessonId});

  factory LessonProgress.fromJson(Map<String, dynamic> j) => LessonProgress(
        current: _int(j['current'], 1),
        total: _int(j['total'], 0),
        mastered: _int(j['mastered'], 0),
        currentLessonId: j['current_lesson_id'] is num ? (j['current_lesson_id'] as num).toInt() : null,
      );

  final int current;
  final int total;
  final int mastered;
  final int? currentLessonId;
}

class HomeSnapshot {
  const HomeSnapshot({required this.userName, required this.lessonProgress});

  factory HomeSnapshot.fromJson(Map<String, dynamic> j) {
    final lp = j['lesson_progress'];
    final name = j['user_name'];
    return HomeSnapshot(
      userName: name is String && name.isNotEmpty ? name : '同学',
      lessonProgress: LessonProgress.fromJson(lp is Map ? Map<String, dynamic>.from(lp) : const {}),
    );
  }

  final String userName;
  final LessonProgress lessonProgress;
}

class StudyTask {
  const StudyTask({
    required this.id,
    required this.subject,
    required this.taskType,
    required this.title,
    required this.detail,
    required this.points,
    required this.submitStatus,
  });

  factory StudyTask.fromJson(Map<String, dynamic> j) => StudyTask(
        id: _int(j['id'], 0),
        subject: (j['subject'] as String?) ?? '',
        taskType: (j['task_type'] as String?) ?? 'custom',
        title: (j['title'] as String?) ?? '',
        detail: (j['detail'] as String?) ?? '',
        points: _int(j['points'], 0),
        submitStatus: (j['submit_status'] as String?) ?? 'not_started',
      );

  final int id;
  final String subject;
  final String taskType;
  final String title;
  final String detail;
  final int points;
  final String submitStatus;
}
```

`lib/features/home/home_logic.dart`：

```dart
import 'package:flutter/material.dart';

import 'data/home_models.dart';

const subjects = ['语文', '英语', '数学'];

bool isDone(StudyTask t) => t.submitStatus == 'approved';

({int done, int total, int percent}) dayProgress(List<StudyTask> tasks) {
  final done = tasks.where(isDone).length;
  final total = tasks.length;
  return (done: done, total: total, percent: total == 0 ? 0 : (done * 100 / total).round());
}

Map<String, ({int done, int total})> subjectProgress(List<StudyTask> tasks) => {
      for (final s in subjects)
        s: (
          done: tasks.where((t) => t.subject == s && isDone(t)).length,
          total: tasks.where((t) => t.subject == s).length,
        ),
    };

int remainingCount(List<StudyTask> tasks, String subject) =>
    tasks.where((t) => t.subject == subject && !isDone(t)).length;

/// 与旧版一致：无学科的任务出现在每个学科下
({List<StudyTask> todo, List<StudyTask> done}) groupForSubject(List<StudyTask> tasks, String subject) {
  final list = tasks.where((t) => t.subject.isEmpty || t.subject == subject).toList();
  return (todo: list.where((t) => !isDone(t)).toList(), done: list.where(isDone).toList());
}

enum TaskAction { done, waiting, openReading, openListening, comingSoon }

TaskAction taskAction(StudyTask t) {
  if (t.submitStatus == 'approved') return TaskAction.done;
  if (t.submitStatus == 'submitted') return TaskAction.waiting;
  if (t.taskType == 'reading') return TaskAction.openReading;
  if (t.taskType == 'listening') return TaskAction.openListening;
  return TaskAction.comingSoon;
}

class TaskMeta {
  const TaskMeta(this.tag, this.minutes, this.icon, this.color);

  final String tag;
  final String minutes;
  final IconData icon;
  final Color color;
}

const _blue = Color(0xFF3158E8);
const _green = Color(0xFF2E8B5A);
const _orange = Color(0xFFDC872D);

const _metas = {
  'dictation': TaskMeta('当前进度', '约 8 分钟', Icons.edit, _blue),
  'knowledge': TaskMeta('重点巩固', '约 10 分钟', Icons.psychology, _green),
  'review': TaskMeta('遗忘曲线', '约 10 分钟', Icons.psychology, _green),
  'reading': TaskMeta('阅读理解', '约 12 分钟', Icons.menu_book, _orange),
  'listening': TaskMeta('听力理解', '约 8 分钟', Icons.headphones, _blue),
  'math': TaskMeta('数学练习', '约 10 分钟', Icons.edit, _orange),
  'custom': TaskMeta('自定义', '', Icons.auto_awesome, _orange),
};

TaskMeta taskMeta(String taskType) => _metas[taskType] ?? _metas['custom']!;

String greeting(int hour) => hour < 6
    ? '夜深了'
    : hour < 12
        ? '早上好'
        : hour < 18
            ? '下午好'
            : '晚上好';

const _week = ['一', '二', '三', '四', '五', '六', '日'];

String dateLabel(DateTime d) => '${d.month} 月 ${d.day} 日，星期${_week[d.weekday - 1]}';

String apiDate(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class Poem {
  const Poem(this.name, this.title, this.text, this.author);

  final String name;
  final String title;
  final String text;
  final String author;
}

/// 与旧版 POEMS 相同，竹/兰/梅/菊按天轮换
const poems = [
  Poem('竹', '竹石', '咬定青山不放松，立根原在破岩中。\n千磨万击还坚劲，任尔东西南北风。', '清 · 郑板桥'),
  Poem('兰', '幽兰', '幽兰在山谷，本自无人识。\n只为馨香重，求者遍山隅。', '陈毅'),
  Poem('梅', '梅花', '墙角数枝梅，凌寒独自开。\n遥知不是雪，为有暗香来。', '宋 · 王安石'),
  Poem('菊', '菊花', '不是花中偏爱菊，此花开尽更无花。', '唐 · 元稹'),
];

Poem todayPoem(DateTime now) => poems[(now.millisecondsSinceEpoch ~/ 86400000) % poems.length];
```

`lib/features/home/data/home_repository.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'home_models.dart';

class HomeRepository {
  HomeRepository(this._api);

  final ApiClient _api;

  Future<HomeSnapshot> snapshot(int userId, String subject) async =>
      HomeSnapshot.fromJson(asMap(await _api.get('/api/home/snapshot', query: {'user_id': userId, 'subject': subject})));

  Future<List<StudyTask>> tasks(int userId, String date) async {
    final list = asList(await _api.get('/api/tasks', query: {'user_id': userId, 'date': date, 'role': 'child'}));
    return [for (final t in list) StudyTask.fromJson(asMap(t))];
  }

  Future<int> balance(int userId) async {
    final d = asMap(await _api.get('/api/points/balance', query: {'user_id': userId}));
    return (d['balance'] as num?)?.toInt() ?? 0;
  }

  /// 返回是否兑换成功（积分不足为 false）
  Future<bool> redeem(int userId, String device, int minutes) async {
    final d = asMap(await _api.post('/api/points/redeem', body: {'user_id': userId, 'device': device, 'minutes': minutes}));
    return d['success'] == true;
  }

  Future<void> submitTask(int taskId) async {
    await _api.post('/api/tasks/$taskId/submit');
  }
}

final homeRepositoryProvider = Provider<HomeRepository>((ref) => HomeRepository(ref.watch(apiClientProvider)));
```

- [ ] **Step 4: 运行测试与静态检查** — `flutter test` 全部通过；`flutter analyze` 无问题。

- [ ] **Step 5: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): 首页数据模型、接口与纯逻辑"
```

---

### Task 5: 首页状态与页面、「我的」积分、外壳刷新

**Files:**
- Create: `lib/features/home/home_controller.dart`、`lib/features/home/ui/home_sections.dart`
- Modify: `lib/features/home/ui/home_page.dart`（替换占位）、`lib/features/profile/ui/profile_page.dart`（加积分）、`lib/features/shell/app_shell.dart`（切回首页刷新）
- Test: `test/features/home/home_page_test.dart`

与学习中心的联动（阅读/听力任务跳转）依赖 Task 7 的 `centerControllerProvider`：本任务中 `openReading` / `openListening` 先调用 `context.go('/center')`，Task 7 再补上 `openForTask`。

- [ ] **Step 1: 写失败的测试**

`test/features/home/home_page_test.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';
import 'package:student_app/features/home/ui/home_page.dart';

class FakeHomeRepository implements HomeRepository {
  FakeHomeRepository({this.fail = false});

  bool fail;
  final snapshotSubjects = <String>[];
  int redeemCalls = 0;
  bool redeemOk = true;
  int balanceValue = 350;

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) async {
    if (fail) throw ApiException('boom');
    snapshotSubjects.add(subject);
    return HomeSnapshot(
      userName: '金同学',
      lessonProgress: LessonProgress(current: subject == '数学' ? 2 : 3, total: 8, mastered: 1, currentLessonId: 46),
    );
  }

  @override
  Future<List<StudyTask>> tasks(int userId, String date) async => const [
        StudyTask(id: 1, subject: '语文', taskType: 'dictation', title: '桂花雨 生词听写', detail: '', points: 20, submitStatus: 'approved'),
        StudyTask(id: 2, subject: '语文', taskType: 'reading', title: '桂花雨 阅读理解', detail: '', points: 20, submitStatus: 'not_started'),
        StudyTask(id: 3, subject: '语文', taskType: 'math', title: '口算练习', detail: '', points: 20, submitStatus: 'not_started'),
        StudyTask(id: 4, subject: '英语', taskType: 'listening', title: '英语听力', detail: '', points: 20, submitStatus: 'submitted'),
      ];

  @override
  Future<int> balance(int userId) async => balanceValue;

  @override
  Future<bool> redeem(int userId, String device, int minutes) async {
    redeemCalls++;
    return redeemOk;
  }

  @override
  Future<void> submitTask(int taskId) async {}
}

Future<void> pumpHome(WidgetTester tester, FakeHomeRepository repo, {Size size = const Size(420, 900)}) async {
  SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final container = ProviderContainer(
    overrides: [homeRepositoryProvider.overrideWithValue(repo)],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(home: Scaffold(body: HomePage())),
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('显示问候、积分、课程与当前学科任务分组', (tester) async {
    await pumpHome(tester, FakeHomeRepository());
    expect(find.textContaining('金同学'), findsWidgets);
    expect(find.text('350'), findsWidgets);
    expect(find.textContaining('第 3 课重点学习与旧课复习'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('桂花雨 阅读理解'), 300);
    expect(find.text('待完成 2'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('已完成 1'), 300);
    expect(find.text('已完成 1'), findsOneWidget);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('task-action-1')), 300);
    expect(find.widgetWithText(FilledButton, '已完成'), findsOneWidget);
    expect(find.text('英语听力'), findsNothing);
  });

  testWidgets('切换学科重新拉取该学科快照', (tester) async {
    final repo = FakeHomeRepository();
    await pumpHome(tester, repo);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('subject-数学')), 300);
    await tester.tap(find.byKey(const ValueKey('subject-数学')));
    await tester.pumpAndSettle();
    expect(repo.snapshotSubjects.last, '数学');
    expect(find.textContaining('第 2 课重点学习与旧课复习'), findsOneWidget);
  });

  testWidgets('未实现的任务类型点击提示即将上线', (tester) async {
    await pumpHome(tester, FakeHomeRepository());
    final btn = find.byKey(const ValueKey('task-action-3'));
    await tester.scrollUntilVisible(btn, 300);
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pump();
    expect(find.text('该练习即将在 App 上线，可先在网页版完成'), findsOneWidget);
  });

  testWidgets('积分兑换成功提示并刷新积分', (tester) async {
    final repo = FakeHomeRepository();
    await pumpHome(tester, repo);
    repo.balanceValue = 50;
    final btn = find.byKey(const ValueKey('redeem-tablet'));
    await tester.scrollUntilVisible(btn, 300);
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pumpAndSettle();
    expect(repo.redeemCalls, 1);
    expect(find.text('已兑换平板 30 分钟，等待家长确认'), findsOneWidget);
    expect(find.text('当前 50 积分'), findsOneWidget);
  });

  testWidgets('加载失败显示重试', (tester) async {
    await pumpHome(tester, FakeHomeRepository(fail: true));
    expect(find.text('重试'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 运行确认失败** — `flutter test test/features/home/home_page_test.dart`。

- [ ] **Step 3: 实现**

`lib/features/home/home_controller.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/home_models.dart';
import 'data/home_repository.dart';
import 'home_logic.dart';

class HomeData {
  const HomeData({required this.subject, required this.snapshot, required this.tasks, required this.points});

  final String subject;
  final HomeSnapshot snapshot;
  final List<StudyTask> tasks;
  final int points;
}

class HomeController extends AsyncNotifier<HomeData> {
  String _subject = subjects.first;

  @override
  Future<HomeData> build() {
    ref.watch(sessionProvider);
    return _load();
  }

  Future<HomeData> _load() async {
    final uid = ref.read(currentChildIdProvider);
    final repo = ref.read(homeRepositoryProvider);
    final results = await Future.wait([
      repo.snapshot(uid, _subject),
      repo.tasks(uid, apiDate(DateTime.now())),
      repo.balance(uid),
    ]);
    return HomeData(
      subject: _subject,
      snapshot: results[0] as HomeSnapshot,
      tasks: results[1] as List<StudyTask>,
      points: results[2] as int,
    );
  }

  Future<void> setSubject(String subject) async {
    if (subject == _subject) return;
    _subject = subject;
    state = await AsyncValue.guard(_load);
  }

  Future<void> reload() async {
    state = await AsyncValue.guard(_load);
  }

  /// 返回提示文案
  Future<String> redeem(String device, int minutes) async {
    final uid = ref.read(currentChildIdProvider);
    final ok = await ref.read(homeRepositoryProvider).redeem(uid, device, minutes);
    if (!ok) return '积分还不够，再完成几个任务吧';
    await reload();
    ref.invalidate(pointsProvider);
    return '已兑换${device == 'tablet' ? '平板' : '手机'} $minutes 分钟，等待家长确认';
  }
}

final homeControllerProvider = AsyncNotifierProvider<HomeController, HomeData>(HomeController.new);

/// 「我的」页积分（以 /api/points/balance 为准）
final pointsProvider = FutureProvider<int>((ref) {
  ref.watch(sessionProvider);
  return ref.read(homeRepositoryProvider).balance(ref.read(currentChildIdProvider));
});
```

`lib/features/home/ui/home_sections.dart`：

```dart
import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../data/home_models.dart';
import '../home_logic.dart';

class GreetingHeader extends StatelessWidget {
  const GreetingHeader({super.key, required this.name, required this.points, required this.now});

  final String name;
  final int points;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(dateLabel(now), style: const TextStyle(color: AppColors.gray)),
          const SizedBox(height: 4),
          Text('${greeting(now.hour)}，$name', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
        ]),
      ),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20), border: Border.all(color: AppColors.line)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.star, color: AppColors.gold, size: 18),
          const SizedBox(width: 4),
          Text('$points', style: const TextStyle(fontWeight: FontWeight.w700)),
          const Text(' 积分', style: TextStyle(fontSize: 12, color: AppColors.gray)),
        ]),
      ),
    ]);
  }
}

class PlanCard extends StatelessWidget {
  const PlanCard({super.key, required this.subject, required this.progress, required this.poem, required this.onStart});

  final String subject;
  final LessonProgress progress;
  final Poem poem;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: AppColors.blue,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('今日个性化学习计划', style: TextStyle(color: Colors.white70)),
          const SizedBox(height: 8),
          Text('第 ${progress.current} 课重点学习与旧课复习',
              style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text('根据今日$subject进度和遗忘曲线，AI 安排了新课巩固与到期复习。', style: const TextStyle(color: Colors.white)),
          const SizedBox(height: 12),
          FilledButton.tonal(onPressed: onStart, child: const Text('开始今日学习')),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.92), borderRadius: BorderRadius.circular(14)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('今日勉励 · ${poem.title}', style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(poem.text, style: const TextStyle(height: 1.6)),
              Align(alignment: Alignment.centerRight, child: Text('—— ${poem.author}', style: const TextStyle(color: AppColors.gray))),
            ]),
          ),
        ]),
      ),
    );
  }
}

class TodayProgressCard extends StatelessWidget {
  const TodayProgressCard({super.key, required this.tasks, required this.lesson});

  final List<StudyTask> tasks;
  final LessonProgress lesson;

  static const _subjectColors = {'语文': AppColors.blue, '英语': AppColors.orange, '数学': AppColors.green};

  @override
  Widget build(BuildContext context) {
    final p = dayProgress(tasks);
    final remain = p.total - p.done;
    final perSubject = subjectProgress(tasks);
    final masteredPct = lesson.total > 0 ? lesson.mastered / lesson.total : 0.0;
    return SectionCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(child: Text('今日进度', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          Text('${p.percent}%', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.blue)),
        ]),
        const SizedBox(height: 6),
        Text('${p.done} / ${p.total} 项'),
        Text(
          remain > 0 ? '还差 $remain 项，今日学习就完成啦' : (p.total > 0 ? '全部完成，今天真棒！' : '今天还没有任务'),
          style: const TextStyle(color: AppColors.gray),
        ),
        const SizedBox(height: 8),
        LinearProgressIndicator(value: p.total == 0 ? 0 : p.done / p.total),
        const SizedBox(height: 12),
        for (final s in subjects) ...[
          Row(children: [
            Expanded(child: Text(s)),
            Text('${perSubject[s]!.done}/${perSubject[s]!.total}', style: const TextStyle(color: AppColors.gray)),
          ]),
          LinearProgressIndicator(
            value: perSubject[s]!.total == 0 ? 0 : perSubject[s]!.done / perSubject[s]!.total,
            color: _subjectColors[s],
          ),
          const SizedBox(height: 8),
        ],
        const Divider(),
        const Text('课程进度', style: TextStyle(fontWeight: FontWeight.w600)),
        Text(
          lesson.total > 0 ? '已学到第 ${lesson.current} 课 · ${lesson.mastered} / ${lesson.total} 课' : '请在家长端导入教材后开始学习',
          style: const TextStyle(color: AppColors.gray),
        ),
        const SizedBox(height: 6),
        LinearProgressIndicator(value: masteredPct),
      ]),
    );
  }
}

class SubjectTabs extends StatelessWidget {
  const SubjectTabs({super.key, required this.tasks, required this.current, required this.onSelect});

  final List<StudyTask> tasks;
  final String current;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Wrap(spacing: 8, children: [
      for (final s in subjects)
        ChoiceChip(
          key: ValueKey('subject-$s'),
          selected: s == current,
          onSelected: (_) => onSelect(s),
          label: Text(remainingCount(tasks, s) > 0 ? '$s ${remainingCount(tasks, s)}' : '$s ✓'),
        ),
    ]);
  }
}

class TaskCard extends StatelessWidget {
  const TaskCard({super.key, required this.task, required this.onAction});

  final StudyTask task;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final meta = taskMeta(task.taskType);
    final action = taskAction(task);
    final label = switch (action) {
      TaskAction.done => '已完成',
      TaskAction.waiting => '等待家长确认',
      _ => '开始练习',
    };
    final enabled = action != TaskAction.done && action != TaskAction.waiting;
    return Opacity(
      opacity: isDone(task) ? 0.6 : 1,
      child: SectionCard(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            CircleAvatar(backgroundColor: meta.color.withValues(alpha: 0.12), child: Icon(meta.icon, color: meta.color)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(meta.tag, style: TextStyle(fontSize: 12, color: meta.color, fontWeight: FontWeight.w600)),
                Text(task.title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                if (task.detail.isNotEmpty) Text(task.detail, style: const TextStyle(color: AppColors.gray)),
              ]),
            ),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            if (meta.minutes.isNotEmpty) Text(meta.minutes, style: const TextStyle(color: AppColors.gray, fontSize: 12)),
            const Spacer(),
            Text('+${task.points}', style: const TextStyle(color: AppColors.gold, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              key: ValueKey('task-action-${task.id}'),
              onPressed: enabled ? onAction : null,
              child: Text(label),
            ),
          ),
        ]),
      ),
    );
  }
}

class RedeemCard extends StatelessWidget {
  const RedeemCard({super.key, required this.points, required this.onRedeem});

  final int points;
  final void Function(String device, int minutes) onRedeem;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('积分兑换 · 劳逸结合，快乐成长', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text('当前 $points 积分', style: const TextStyle(color: AppColors.gray)),
        const SizedBox(height: 12),
        Wrap(spacing: 12, runSpacing: 12, children: [
          OutlinedButton.icon(
            key: const ValueKey('redeem-tablet'),
            onPressed: () => onRedeem('tablet', 30),
            icon: const Icon(Icons.tablet_mac),
            label: const Text('平板 30 分钟 · 300 积分'),
          ),
          OutlinedButton.icon(
            key: const ValueKey('redeem-phone'),
            onPressed: () => onRedeem('phone', 20),
            icon: const Icon(Icons.phone_android),
            label: const Text('手机 20 分钟 · 200 积分'),
          ),
        ]),
      ]),
    );
  }
}

class WeeklyPlaceholderCard extends StatelessWidget {
  const WeeklyPlaceholderCard({super.key});

  @override
  Widget build(BuildContext context) => const SectionCard(
        child: Row(children: [
          Expanded(child: Text('本周学习', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          Text('暂无记录', style: TextStyle(color: AppColors.gray)),
        ]),
      );
}
```

`lib/features/home/ui/home_page.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets.dart';
import '../data/home_models.dart';
import '../home_controller.dart';
import '../home_logic.dart';
import 'home_sections.dart';

class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  final _tasksKey = GlobalKey();

  void _onTask(StudyTask t) {
    switch (taskAction(t)) {
      case TaskAction.openReading:
      case TaskAction.openListening:
        context.go('/center');
      case TaskAction.comingSoon:
        showMessage(context, '该练习即将在 App 上线，可先在网页版完成');
      case TaskAction.done:
      case TaskAction.waiting:
        break;
    }
  }

  Future<void> _redeem(String device, int minutes) async {
    try {
      final msg = await ref.read(homeControllerProvider.notifier).redeem(device, minutes);
      if (mounted) showMessage(context, msg);
    } catch (_) {
      if (mounted) showMessage(context, '兑换失败，请稍后重试');
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(homeControllerProvider);
    final data = async.value;
    if (data == null) {
      if (async.hasError) {
        return ErrorCard(
          message: '首页加载失败，请检查网络或后端服务',
          onRetry: () => ref.read(homeControllerProvider.notifier).reload(),
        );
      }
      return const Center(child: CircularProgressIndicator());
    }
    final now = DateTime.now();
    final groups = groupForSubject(data.tasks, data.subject);
    return LayoutBuilder(builder: (context, c) {
      final wide = c.maxWidth >= 840;
      final columns = c.maxWidth >= 1100 ? 3 : (c.maxWidth >= 600 ? 2 : 1);
      Widget grid(List<StudyTask> list) => _TaskGrid(columns: columns, children: [
            for (final t in list) TaskCard(task: t, onAction: () => _onTask(t)),
          ]);
      final plan = PlanCard(
        subject: data.subject,
        progress: data.snapshot.lessonProgress,
        poem: todayPoem(now),
        onStart: () {
          final ctx = _tasksKey.currentContext;
          if (ctx != null) Scrollable.ensureVisible(ctx, duration: const Duration(milliseconds: 300));
        },
      );
      final progress = TodayProgressCard(tasks: data.tasks, lesson: data.snapshot.lessonProgress);
      return RefreshIndicator(
        onRefresh: () => ref.read(homeControllerProvider.notifier).reload(),
        child: ListView(padding: const EdgeInsets.all(20), children: [
          GreetingHeader(name: data.snapshot.userName, points: data.points, now: now),
          const SizedBox(height: 16),
          if (wide)
            IntrinsicHeight(
              child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Expanded(flex: 3, child: plan),
                const SizedBox(width: 16),
                Expanded(flex: 2, child: progress),
              ]),
            )
          else ...[
            plan,
            const SizedBox(height: 16),
            progress,
          ],
          const SizedBox(height: 24),
          Row(key: _tasksKey, children: [
            const Expanded(child: Text('今日学习任务', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700))),
          ]),
          const SizedBox(height: 8),
          SubjectTabs(
            tasks: data.tasks,
            current: data.subject,
            onSelect: (s) => ref.read(homeControllerProvider.notifier).setSubject(s),
          ),
          const SizedBox(height: 12),
          if (groups.todo.isEmpty && groups.done.isEmpty)
            const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('今天还没有任务，先去学习中心看看吧')))
          else ...[
            Text('待完成 ${groups.todo.length}', style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (groups.todo.isEmpty)
              const Padding(padding: EdgeInsets.all(12), child: Text('本学科任务都完成啦，去别的学科看看吧 🎉'))
            else
              grid(groups.todo),
            if (groups.done.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text('已完成 ${groups.done.length}', style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              grid(groups.done),
            ],
          ],
          const SizedBox(height: 24),
          const WeeklyPlaceholderCard(),
          const SizedBox(height: 16),
          RedeemCard(points: data.points, onRedeem: _redeem),
        ]),
      );
    });
  }
}

class _TaskGrid extends StatelessWidget {
  const _TaskGrid({required this.columns, required this.children});

  final int columns;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      const gap = 12.0;
      final width = (c.maxWidth - gap * (columns - 1)) / columns;
      return Wrap(spacing: gap, runSpacing: gap, children: [
        for (final w in children) SizedBox(width: width, child: w),
      ]);
    });
  }
}
```

`lib/features/profile/ui/profile_page.dart` 改为显示积分（在名字行下方）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../auth/session.dart';
import '../../home/home_controller.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final child = ref.watch(sessionProvider).value;
    final points = ref.watch(pointsProvider);
    return ListView(padding: const EdgeInsets.all(20), children: [
      SectionCard(
        child: Row(children: [
          CircleAvatar(radius: 26, child: Text(child == null ? '' : child.name.characters.last)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(child?.name ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              Text(
                points.when(data: (p) => '$p 积分', loading: () => '积分加载中…', error: (_, _) => '积分加载失败'),
                style: const TextStyle(color: AppColors.gray),
              ),
            ]),
          ),
        ]),
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () => ref.read(sessionProvider.notifier).logout(),
        icon: const Icon(Icons.logout),
        label: const Text('退出登录'),
      ),
    ]);
  }
}
```

`lib/features/shell/app_shell.dart`：在 `_AppShellState` 中加 Tab 切换联动（`build` 开头检测 `currentIndex` 变化，帧后执行），并新增 import `../home/home_controller.dart`：

```dart
  int? _lastIndex;

  void _onIndexChanged(int? from, int to) {
    if (from == null) return;
    if (to == 0) ref.read(homeControllerProvider.notifier).reload();
    if (to == 2) ref.invalidate(pointsProvider);
  }
```

并在 `build` 开头（`final index = ...` 之后）加入：

```dart
    if (_lastIndex != index) {
      final from = _lastIndex;
      _lastIndex = index;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _onIndexChanged(from, index);
      });
    }
```

- [ ] **Step 4: 运行测试与静态检查** — `flutter test` 全部通过；`flutter analyze` 无问题。

- [ ] **Step 5: 冒烟运行** — `flutter run -d chrome` 登录后首页数据与旧版学生端（`http://127.0.0.1:8766`）一致：积分、第几课、今日进度、各学科任务分组、学科切换。

- [ ] **Step 6: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): 学习首页（进度、任务分组、学科切换、积分兑换）与我的页积分"
```

---

### Task 6: 学习中心数据层、自动提交逻辑与朗读

**Files:**
- Create: `lib/features/center/data/center_models.dart`、`lib/features/center/data/center_repository.dart`、`lib/features/center/center_logic.dart`、`lib/features/center/speech_player.dart`
- Test: `test/features/center/center_logic_test.dart`、`test/features/center/center_repository_test.dart`

- [ ] **Step 1: 写失败的测试**

`test/features/center/center_logic_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';

void main() {
  bool check({CenterTab? taskTab = CenterTab.reading, CenterTab current = CenterTab.reading, int count = 2, int answered = 2, bool submitting = false}) =>
      shouldAutoSubmit(taskTab: taskTab, currentTab: current, questionCount: count, answeredCount: answered, submitting: submitting);

  test('自动提交条件', () {
    expect(check(), isTrue);
    expect(check(taskTab: null), isFalse);
    expect(check(current: CenterTab.listening), isFalse);
    expect(check(count: 0, answered: 0), isFalse);
    expect(check(answered: 1), isFalse);
    expect(check(submitting: true), isFalse);
  });

  test('答案比对去首尾空白后全等', () {
    expect(isCorrectAnswer(' 相等 ', '相等'), isTrue);
    expect(isCorrectAnswer('不相等', '相等'), isFalse);
  });

  test('材料解析与空材料', () {
    final m = CenterMaterial.fromJson({
      'text': 'Hello.\nHi.',
      'questions': [{'question': 'Q1', 'answer': 'A1'}],
    });
    expect(m.text, 'Hello.\nHi.');
    expect(m.questions.single.question, 'Q1');
    expect(m.isEmpty, isFalse);
    expect(CenterMaterial.fromJson({'text': '', 'questions': []}).isEmpty, isTrue);
    expect(CenterMaterial.empty.questions, isEmpty);
  });

  test('朗读语言：含英文字母用 en-US', () {
    expect(speechLanguage('Hello'), 'en-US');
    expect(speechLanguage('你好'), 'zh-CN');
  });
}
```

`test/features/center/center_repository_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/center/data/center_repository.dart';

class FakeApi implements ApiClient {
  final calls = <String>[];
  Object? Function(String path, Map<String, dynamic>? query)? onGet;

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    calls.add('GET $path $query');
    return onGet!(path, query);
  }

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    calls.add('POST $path $body');
    return {'ok': true};
  }

  @override
  Future<({List<int> bytes, String contentType})> getBytes(String path, {Map<String, dynamic>? query}) =>
      throw UnimplementedError();
}

void main() {
  test('阅读用语文快照的当前课；缺失时返回空材料且不请求阅读接口', () async {
    final api = FakeApi()
      ..onGet = (path, q) => path == '/api/home/snapshot'
          ? {'lesson_progress': {'current_lesson_id': null}}
          : throw StateError('should not request $path');
    final m = await CenterRepository(api).reading(4);
    expect(m.isEmpty, isTrue);
    expect(api.calls.single, contains('subject: 语文'));
  });

  test('阅读材料按当前课请求', () async {
    final api = FakeApi()
      ..onGet = (path, q) => path == '/api/home/snapshot'
          ? {'lesson_progress': {'current_lesson_id': 46}}
          : {'text': '课文', 'questions': [{'question': 'Q', 'answer': 'A'}]};
    final m = await CenterRepository(api).reading(4);
    expect(m.text, '课文');
    expect(api.calls.last, contains('lesson_id: 46'));
  });

  test('答错收录错题本', () async {
    final api = FakeApi();
    await CenterRepository(api).submitWrong(userId: 4, question: 'Q', yourAnswer: 'x', correctAnswer: 'A', sourceType: 'reading');
    expect(api.calls.single, startsWith('POST /api/review/submit'));
    expect(api.calls.single, contains('source_type: reading'));
  });
}
```

- [ ] **Step 2: 运行确认失败** — `flutter test test/features/center`。

- [ ] **Step 3: 实现**

`lib/features/center/data/center_models.dart`：

```dart
class CenterQuestion {
  const CenterQuestion(this.question, this.answer);

  final String question;
  final String answer;
}

class CenterMaterial {
  const CenterMaterial({required this.text, required this.questions});

  factory CenterMaterial.fromJson(Map<String, dynamic> j) {
    final qs = j['questions'];
    return CenterMaterial(
      text: (j['text'] as String?) ?? '',
      questions: [
        if (qs is List)
          for (final q in qs.whereType<Map>()) CenterQuestion('${q['question'] ?? ''}', '${q['answer'] ?? ''}'),
      ],
    );
  }

  static const empty = CenterMaterial(text: '', questions: []);

  final String text;
  final List<CenterQuestion> questions;

  bool get isEmpty => text.isEmpty || questions.isEmpty;
}
```

`lib/features/center/center_logic.dart`：

```dart
enum CenterTab { listening, reading }

extension CenterTabX on CenterTab {
  String get label => this == CenterTab.listening ? '听力理解' : '阅读理解';
  String get sourceType => this == CenterTab.listening ? 'listening' : 'reading';
}

/// 仅当在任务对应的 Tab、题目数 > 0、全部作答且不在提交中时自动提交任务
bool shouldAutoSubmit({
  required CenterTab? taskTab,
  required CenterTab currentTab,
  required int questionCount,
  required int answeredCount,
  required bool submitting,
}) =>
    taskTab != null && taskTab == currentTab && questionCount > 0 && answeredCount >= questionCount && !submitting;

bool isCorrectAnswer(String input, String answer) => input.trim() == answer.trim();

String speechLanguage(String text) => RegExp('[a-zA-Z]').hasMatch(text) ? 'en-US' : 'zh-CN';
```

`lib/features/center/data/center_repository.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'center_models.dart';

class CenterRepository {
  CenterRepository(this._api);

  final ApiClient _api;

  Future<CenterMaterial> listening(int userId) async =>
      CenterMaterial.fromJson(asMap(await _api.get('/api/listening/material', query: {'user_id': userId})));

  /// 阅读取语文快照的当前课；没有当前课时返回空材料
  Future<CenterMaterial> reading(int userId) async {
    final snap = asMap(await _api.get('/api/home/snapshot', query: {'user_id': userId, 'subject': '语文'}));
    final lp = snap['lesson_progress'];
    final lessonId = lp is Map && lp['current_lesson_id'] is num ? (lp['current_lesson_id'] as num).toInt() : null;
    if (lessonId == null) return CenterMaterial.empty;
    return CenterMaterial.fromJson(asMap(await _api.get('/api/reading/material', query: {'lesson_id': lessonId})));
  }

  Future<void> submitWrong({
    required int userId,
    required String question,
    required String yourAnswer,
    required String correctAnswer,
    required String sourceType,
  }) async {
    await _api.post('/api/review/submit', body: {
      'user_id': userId,
      'question': question,
      'your_answer': yourAnswer,
      'correct_answer': correctAnswer,
      'source_type': sourceType,
    });
  }
}

final centerRepositoryProvider = Provider<CenterRepository>((ref) => CenterRepository(ref.watch(apiClientProvider)));
```

`lib/features/center/speech_player.dart`：

```dart
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import 'center_logic.dart';

abstract class SpeechPlayer {
  Future<void> speak(String text);
}

/// 优先播放后端 TTS 音频；后端为 fake、出错或网络失败时用设备朗读（对应旧版 speechSynthesis）
class BackendSpeechPlayer implements SpeechPlayer {
  BackendSpeechPlayer(this._api);

  final ApiClient _api;
  final AudioPlayer _audio = AudioPlayer();
  final FlutterTts _tts = FlutterTts();

  @override
  Future<void> speak(String raw) async {
    final text = raw.replaceAll('\n', ' ');
    try {
      final r = await _api.getBytes('/api/tts/synthesize', query: {'text': text});
      if (r.contentType.startsWith('audio/')) {
        await _audio.play(BytesSource(Uint8List.fromList(r.bytes), mimeType: 'audio/mpeg'));
        return;
      }
    } catch (_) {
      // 落到设备朗读
    }
    await _tts.setLanguage(speechLanguage(text));
    // 旧版浏览器语速 0.9；flutter_tts 在安卓上 0.5 为正常语速
    await _tts.setSpeechRate(kIsWeb ? 0.9 : 0.45);
    await _tts.speak(text);
  }
}

final speechPlayerProvider = Provider<SpeechPlayer>((ref) => BackendSpeechPlayer(ref.watch(apiClientProvider)));
```

- [ ] **Step 4: 运行测试与静态检查** — `flutter test` 全部通过；`flutter analyze` 无问题。

- [ ] **Step 5: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): 学习中心数据层、自动提交条件与朗读"
```

---

### Task 7: 学习中心状态与页面，首页任务跳转联动

**Files:**
- Create: `lib/features/center/center_controller.dart`
- Modify: `lib/features/center/ui/center_page.dart`（替换占位）、`lib/features/home/ui/home_page.dart`（`_onTask` 调用 `openForTask`）、`lib/features/shell/app_shell.dart`（进入/离开学习中心）
- Test: `test/features/center/center_controller_test.dart`

- [ ] **Step 1: 写失败的测试**

`test/features/center/center_controller_test.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/center/center_controller.dart';
import 'package:student_app/features/center/center_logic.dart';
import 'package:student_app/features/center/data/center_models.dart';
import 'package:student_app/features/center/data/center_repository.dart';
import 'package:student_app/features/home/data/home_models.dart';
import 'package:student_app/features/home/data/home_repository.dart';

class FakeCenterRepository implements CenterRepository {
  CenterMaterial readingMaterial = const CenterMaterial(text: '课文', questions: [CenterQuestion('Q1', 'A1'), CenterQuestion('Q2', 'A2')]);
  CenterMaterial listeningMaterial = const CenterMaterial(text: 'Hi', questions: [CenterQuestion('L1', 'yes')]);
  final wrong = <String>[];

  @override
  Future<CenterMaterial> listening(int userId) async => listeningMaterial;

  @override
  Future<CenterMaterial> reading(int userId) async => readingMaterial;

  @override
  Future<void> submitWrong({required int userId, required String question, required String yourAnswer, required String correctAnswer, required String sourceType}) async {
    wrong.add('$sourceType:$question:$yourAnswer');
  }
}

class FakeTaskRepository implements HomeRepository {
  final submitted = <int>[];

  @override
  Future<void> submitTask(int taskId) async => submitted.add(taskId);

  @override
  Future<HomeSnapshot> snapshot(int userId, String subject) => throw UnimplementedError();
  @override
  Future<List<StudyTask>> tasks(int userId, String date) => throw UnimplementedError();
  @override
  Future<int> balance(int userId) => throw UnimplementedError();
  @override
  Future<bool> redeem(int userId, String device, int minutes) => throw UnimplementedError();
}

Future<(ProviderContainer, FakeCenterRepository, FakeTaskRepository)> setup() async {
  SharedPreferences.setMockInitialValues({'knoact_child_id': 4, 'knoact_child_name': '金同学'});
  final center = FakeCenterRepository();
  final tasks = FakeTaskRepository();
  final c = ProviderContainer(
    overrides: [
      centerRepositoryProvider.overrideWithValue(center),
      homeRepositoryProvider.overrideWithValue(tasks),
    ],
    retry: (_, _) => null,
  );
  addTearDown(c.dispose);
  await c.read(sessionProvider.future);
  return (c, center, tasks);
}

void main() {
  test('进入时加载当前 Tab 材料并清空作答', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.enter();
    final s = c.read(centerControllerProvider);
    expect(s.tab, CenterTab.listening);
    expect(s.material.value!.questions.length, 1);
    expect(s.results, [null]);
  });

  test('答错收录错题本并提示，答对提示正确', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.selectTab(CenterTab.reading);
    await ctl.answer(0, 'x');
    expect(center.wrong, ['reading:Q1:x']);
    expect(c.read(centerControllerProvider).message, '答错了，已收录进错题本');
    await ctl.answer(1, ' A2 ');
    expect(c.read(centerControllerProvider).message, '回答正确！');
    expect(c.read(centerControllerProvider).results, [false, true]);
  });

  test('从任务进入：在任务对应 Tab 全部作答后自动提交一次', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    expect(c.read(centerControllerProvider).tab, CenterTab.reading);
    await ctl.answer(0, 'A1');
    expect(tasks.submitted, isEmpty);
    await ctl.answer(1, 'A2');
    expect(tasks.submitted, [85]);
    expect(c.read(centerControllerProvider).message, '已提交，等待家长确认');
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('切到别的 Tab 后清除待提交任务', () async {
    final (c, _, tasks) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    await ctl.selectTab(CenterTab.listening);
    expect(c.read(centerControllerProvider).pending, isNull);
    await ctl.selectTab(CenterTab.reading);
    await ctl.answer(0, 'A1');
    await ctl.answer(1, 'A2');
    expect(tasks.submitted, isEmpty);
  });

  test('离开学习中心清除待提交任务', () async {
    final (c, _, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    ctl.leave();
    expect(c.read(centerControllerProvider).pending, isNull);
  });

  test('材料为空时不提交并提示', () async {
    final (c, center, tasks) = await setup();
    center.readingMaterial = CenterMaterial.empty;
    final ctl = c.read(centerControllerProvider.notifier);
    ctl.openForTask(85, CenterTab.reading);
    await ctl.enter();
    expect(c.read(centerControllerProvider).message, '暂无材料，暂时无法完成该任务');
    expect(tasks.submitted, isEmpty);
  });

  test('同一题只能作答一次', () async {
    final (c, center, _) = await setup();
    final ctl = c.read(centerControllerProvider.notifier);
    await ctl.selectTab(CenterTab.reading);
    await ctl.answer(0, 'x');
    await ctl.answer(0, 'y');
    expect(center.wrong.length, 1);
  });
}
```

- [ ] **Step 2: 运行确认失败** — `flutter test test/features/center/center_controller_test.dart`。

- [ ] **Step 3: 实现**

`lib/features/center/center_controller.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../home/data/home_repository.dart';
import 'center_logic.dart';
import 'data/center_models.dart';
import 'data/center_repository.dart';

class PendingTask {
  const PendingTask(this.taskId, this.tab);

  final int taskId;
  final CenterTab tab;
}

class CenterState {
  const CenterState({
    this.tab = CenterTab.listening,
    this.material = const AsyncLoading<CenterMaterial>(),
    this.inputs = const [],
    this.results = const [],
    this.pending,
    this.submitting = false,
    this.message,
    this.messageSeq = 0,
  });

  final CenterTab tab;
  final AsyncValue<CenterMaterial> material;
  final List<String> inputs;

  /// 每题作答结果：null 未作答，true/false 对错
  final List<bool?> results;
  final PendingTask? pending;
  final bool submitting;
  final String? message;
  final int messageSeq;

  CenterState copyWith({
    CenterTab? tab,
    AsyncValue<CenterMaterial>? material,
    List<String>? inputs,
    List<bool?>? results,
    PendingTask? Function()? pending,
    bool? submitting,
  }) =>
      CenterState(
        tab: tab ?? this.tab,
        material: material ?? this.material,
        inputs: inputs ?? this.inputs,
        results: results ?? this.results,
        pending: pending != null ? pending() : this.pending,
        submitting: submitting ?? this.submitting,
        message: message,
        messageSeq: messageSeq,
      );

  CenterState withMessage(String text) => CenterState(
        tab: tab,
        material: material,
        inputs: inputs,
        results: results,
        pending: pending,
        submitting: submitting,
        message: text,
        messageSeq: messageSeq + 1,
      );
}

class CenterController extends Notifier<CenterState> {
  int _loadToken = 0;

  @override
  CenterState build() => const CenterState();

  /// 首页点阅读/听力任务时调用，随后跳转到学习中心
  void openForTask(int taskId, CenterTab tab) {
    state = state.copyWith(tab: tab, pending: () => PendingTask(taskId, tab));
  }

  /// 进入学习中心：重新拉取当前 Tab 材料并清空作答
  Future<void> enter() => _load(state.tab);

  void leave() {
    state = state.copyWith(pending: () => null);
  }

  Future<void> selectTab(CenterTab tab) {
    if (state.pending != null && state.pending!.tab != tab) {
      state = state.copyWith(pending: () => null);
    }
    return _load(tab);
  }

  Future<void> reload() => _load(state.tab);

  Future<void> _load(CenterTab tab) async {
    final token = ++_loadToken;
    state = state.copyWith(tab: tab, material: const AsyncLoading(), inputs: const [], results: const []);
    final uid = ref.read(currentChildIdProvider);
    final repo = ref.read(centerRepositoryProvider);
    final result = await AsyncValue.guard(
      () => tab == CenterTab.listening ? repo.listening(uid) : repo.reading(uid),
    );
    if (token != _loadToken) return;
    final count = result.value?.questions.length ?? 0;
    state = state.copyWith(
      material: result,
      inputs: List.filled(count, ''),
      results: List<bool?>.filled(count, null),
    );
    final m = result.value;
    if (m != null && m.isEmpty && state.pending?.tab == tab) {
      state = state.withMessage('暂无材料，暂时无法完成该任务');
    }
  }

  void setInput(int index, String value) {
    final inputs = [...state.inputs];
    inputs[index] = value;
    state = state.copyWith(inputs: inputs);
  }

  Future<void> answer(int index, String input) async {
    final m = state.material.value;
    if (m == null || index >= m.questions.length || state.results[index] != null) return;
    final q = m.questions[index];
    final ok = isCorrectAnswer(input, q.answer);
    final results = [...state.results]..[index] = ok;
    final inputs = [...state.inputs]..[index] = input;
    state = state.copyWith(results: results, inputs: inputs);
    if (ok) {
      state = state.withMessage('回答正确！');
    } else {
      try {
        await ref.read(centerRepositoryProvider).submitWrong(
              userId: ref.read(currentChildIdProvider),
              question: q.question,
              yourAnswer: input,
              correctAnswer: q.answer,
              sourceType: state.tab.sourceType,
            );
        state = state.withMessage('答错了，已收录进错题本');
      } catch (_) {
        state = state.withMessage('答错了（收录错题本失败，请稍后重试）');
      }
    }
    await _maybeSubmitTask();
  }

  Future<void> _maybeSubmitTask() async {
    final m = state.material.value;
    final pending = state.pending;
    final answered = state.results.where((r) => r != null).length;
    if (!shouldAutoSubmit(
      taskTab: pending?.tab,
      currentTab: state.tab,
      questionCount: m?.questions.length ?? 0,
      answeredCount: answered,
      submitting: state.submitting,
    )) {
      return;
    }
    state = state.copyWith(submitting: true);
    try {
      await ref.read(homeRepositoryProvider).submitTask(pending!.taskId);
      state = state.copyWith(pending: () => null, submitting: false).withMessage('已提交，等待家长确认');
    } catch (_) {
      state = state.copyWith(submitting: false).withMessage('提交任务失败，请稍后重试');
    }
  }
}

final centerControllerProvider = NotifierProvider<CenterController, CenterState>(CenterController.new);
```

`lib/features/center/ui/center_page.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../center_controller.dart';
import '../center_logic.dart';
import '../data/center_models.dart';
import '../speech_player.dart';

class CenterPage extends ConsumerWidget {
  const CenterPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(centerControllerProvider.select((s) => s.messageSeq), (prev, next) {
      final msg = ref.read(centerControllerProvider).message;
      if (msg != null && prev != next) showMessage(context, msg);
    });
    final s = ref.watch(centerControllerProvider);
    final ctl = ref.read(centerControllerProvider.notifier);
    return ListView(padding: const EdgeInsets.all(20), children: [
      const Text('学习中心', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
      const SizedBox(height: 12),
      SegmentedButton<CenterTab>(
        segments: [
          for (final t in CenterTab.values)
            ButtonSegment(
              value: t,
              label: Text(t.label),
              icon: Icon(t == CenterTab.listening ? Icons.headphones : Icons.menu_book),
            ),
        ],
        selected: {s.tab},
        onSelectionChanged: (v) => ctl.selectTab(v.first),
      ),
      const SizedBox(height: 16),
      s.material.when(
        loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
        error: (_, _) => ErrorCard(message: '材料加载失败，请检查网络或后端服务', onRetry: ctl.reload),
        data: (m) => m.isEmpty ? _Empty(tab: s.tab) : _MaterialView(state: s, material: m),
      ),
    ]);
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.tab});

  final CenterTab tab;

  @override
  Widget build(BuildContext context) => SectionCard(
        child: Column(children: [
          Icon(tab == CenterTab.listening ? Icons.headphones : Icons.menu_book, size: 32, color: AppColors.gray),
          const SizedBox(height: 8),
          Text(
            tab == CenterTab.listening ? '暂无听力材料，AI 将根据学习进度生成对话' : '暂无阅读材料，请在家长端导入教材',
            style: const TextStyle(color: AppColors.gray),
          ),
        ]),
      );
}

class _MaterialView extends ConsumerWidget {
  const _MaterialView({required this.state, required this.material});

  final CenterState state;
  final CenterMaterial material;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final listening = state.tab == CenterTab.listening;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SectionCard(
        child: listening
            ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('听力对话', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () => ref.read(speechPlayerProvider).speak(material.text),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('播放对话'),
                ),
                const SizedBox(height: 6),
                const Text('认真听，不要看文本哦', style: TextStyle(color: AppColors.gray)),
              ])
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('阅读课文', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                Text(material.text, style: const TextStyle(height: 1.7)),
              ]),
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < material.questions.length; i++) ...[
        _QuestionCard(index: i, question: material.questions[i], result: state.results[i], input: state.inputs[i]),
        const SizedBox(height: 12),
      ],
    ]);
  }
}

class _QuestionCard extends ConsumerStatefulWidget {
  const _QuestionCard({required this.index, required this.question, required this.result, required this.input});

  final int index;
  final CenterQuestion question;
  final bool? result;
  final String input;

  @override
  ConsumerState<_QuestionCard> createState() => _QuestionCardState();
}

class _QuestionCardState extends ConsumerState<_QuestionCard> {
  late final TextEditingController _ctl = TextEditingController(text: widget.input);

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.question;
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${widget.index + 1}. ${q.question}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (widget.result == null)
          Row(children: [
            Expanded(
              child: TextField(
                key: ValueKey('answer-${widget.index}'),
                controller: _ctl,
                decoration: const InputDecoration(hintText: '输入你的答案', isDense: true, border: OutlineInputBorder()),
                onChanged: (v) => ref.read(centerControllerProvider.notifier).setInput(widget.index, v),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              key: ValueKey('submit-${widget.index}'),
              onPressed: () => ref.read(centerControllerProvider.notifier).answer(widget.index, _ctl.text),
              child: const Text('提交'),
            ),
          ])
        else
          Text(
            '${widget.result! ? '✓' : '✗'} 答案：${q.answer}',
            style: TextStyle(color: widget.result! ? AppColors.green : Colors.red, fontWeight: FontWeight.w600),
          ),
      ]),
    );
  }
}
```

`lib/features/home/ui/home_page.dart`：`_onTask` 中阅读/听力分支改为先 `openForTask` 再跳转，并新增 import `../../center/center_controller.dart`、`../../center/center_logic.dart`：

```dart
      case TaskAction.openReading:
        ref.read(centerControllerProvider.notifier).openForTask(t.id, CenterTab.reading);
        context.go('/center');
      case TaskAction.openListening:
        ref.read(centerControllerProvider.notifier).openForTask(t.id, CenterTab.listening);
        context.go('/center');
```

`lib/features/shell/app_shell.dart`：`_onIndexChanged` 改为（新增 import `../center/center_controller.dart`）：

```dart
  void _onIndexChanged(int? from, int to) {
    if (from == 1 && to != 1) ref.read(centerControllerProvider.notifier).leave();
    if (to == 1) ref.read(centerControllerProvider.notifier).enter();
    if (from == null) return;
    if (to == 0) ref.read(homeControllerProvider.notifier).reload();
    if (to == 2) ref.invalidate(pointsProvider);
  }
```

（首次进入应用即停在学习中心时 `from == null`，也会加载材料。）

- [ ] **Step 4: 运行测试与静态检查** — `flutter test` 全部通过；`flutter analyze` 无问题。

- [ ] **Step 5: 冒烟运行** — `flutter run -d chrome`：学习中心听力「播放对话」有声音（后端 TTS 或设备朗读），阅读显示课文；答错提示收录错题本（家长端/旧版错题本可见）；首页点阅读任务 → 学习中心阅读 Tab → 全部答完提示已提交 → 回首页该任务显示「等待家长确认」。

- [ ] **Step 6: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): 学习中心听力与阅读答题、任务自动提交与首页联动"
```

---

### Task 8: Web 部署（Docker + nginx）与文档

**Files:**
- Create: `student-app/Dockerfile`、`student-app/nginx.conf`、`student-app/.dockerignore`
- Modify: `docker-compose.yml`、`.env.example`、`README.md`、根目录 `.dockerignore`

- [ ] **Step 1: `student-app/Dockerfile`**

```dockerfile
# KnoAct Flutter 学生端（Web）
# 构建上下文为 student-app/：docker build -t knoact-student-app ./student-app
FROM ghcr.io/cirruslabs/flutter:3.47.9 AS build
# 国内网络：pub 与 Flutter 资源走镜像
ENV PUB_HOSTED_URL=https://pub.flutter-io.cn \
    FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get
COPY . .
# API_BASE 置空：Web 走同源，经 nginx 反代 /api、/uploads 到后端
RUN flutter build web --release --dart-define=API_BASE=

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html
EXPOSE 80
```

- [ ] **Step 2: `student-app/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    client_max_body_size 200m;

    location /api/ {
        proxy_pass http://backend:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection "";
        # 听力/阅读材料与 TTS 可能当场调用大模型生成
        proxy_buffering off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location /uploads/ {
        proxy_pass http://backend:8010;
        proxy_set_header Host $host;
    }

    location = /health {
        proxy_pass http://backend:8010;
    }

    # 发版后浏览器须拿到新版本：入口与引导脚本不缓存
    location ~ ^/(index\.html|flutter_bootstrap\.js|flutter_service_worker\.js|main\.dart\.js|version\.json)$ {
        add_header Cache-Control "no-cache";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: `student-app/.dockerignore`**

```
build/
.dart_tool/
android/
.idea/
*.iml
```

- [ ] **Step 4: docker-compose 与环境变量**

`docker-compose.yml` 在 `parent-web:` 服务块之后插入：

```yaml
  student-app:
    build: ./student-app
    image: knoact-student-app:latest
    restart: unless-stopped
    ports:
      - "${KNOACT_STUDENT_PORT:-8082}:80"
    depends_on:
      backend:
        condition: service_healthy
```

文件头部服务说明加一行 `#   student-app Flutter 学生端（Web），功能对齐后替代 frontend`，并把「两个前端均由 nginx 托管…」改为「三个前端均由 nginx 托管…」；「访问」行改为：
`# 访问：学生端（Flutter）http://<服务器IP>:${KNOACT_STUDENT_PORT:-8082}，旧版学生端 :${KNOACT_HTTP_PORT:-8080}，家长端 :${KNOACT_PARENT_PORT:-8081}`

`.env.example` 在 `KNOACT_PARENT_PORT=8081` 之后加：

```bash

# Flutter 学生端（Web）对外端口：http://<服务器IP>:8082
KNOACT_STUDENT_PORT=8082
```

根目录 `.dockerignore` 加一行 `student-app/`（render 构建上下文不需要）。

- [ ] **Step 5: README**

- 「目录结构」加 `student-app/      Flutter 学生端（Web + Android，逐步替代 frontend/）`。
- 「服务与数据」表加 `| student-app | Flutter 学生端（Web），nginx 托管并反代 /api、/uploads | 对外 8082 |`；启动一节访问地址加 Flutter 学生端 8082。
- 「配置」表加 `| KNOACT_STUDENT_PORT | 8082 | docker 部署的 Flutter 学生端对外端口 |`。
- 「本地开发」新增「Flutter 学生端」小节：

  ```bash
  cd student-app
  flutter pub get
  flutter run -d chrome                                            # Web，连本地后端 127.0.0.1:8010
  flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8010   # 安卓模拟器
  flutter test && flutter analyze
  ```

  并说明：国内网络设置 `PUB_HOSTED_URL=https://pub.flutter-io.cn`、`FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn`。

- [ ] **Step 6: 校验与提交**

Run（仓库根目录）: `py -c "import yaml;d=yaml.safe_load(open('docker-compose.yml',encoding='utf-8'));print(list(d['services']), d['services']['student-app']['ports'])"`
Expected: 含 `student-app`，端口 `['${KNOACT_STUDENT_PORT:-8082}:80']`。

```bash
git -C D:\workspace\github\KnoAct add student-app/Dockerfile student-app/nginx.conf student-app/.dockerignore docker-compose.yml .env.example README.md .dockerignore
git -C D:\workspace\github\KnoAct commit -m "feat: docker-compose 新增 Flutter 学生端 student-app 服务，README 更新"
```

---

### Task 9: 安卓配置与构建

**Files:**
- Modify: `student-app/android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1: 网络权限与明文 HTTP**

在 `<manifest>` 内、`<application>` 之前加：

```xml
    <uses-permission android:name="android.permission.INTERNET"/>
```

`<application ...>` 标签加属性 `android:usesCleartextTraffic="true"`（连接本地/内网 HTTP 后端）。

flutter_tts 在 Android 11+ 需声明朗读服务：在模板已有的 `<queries>` 内加：

```xml
        <intent>
            <action android:name="android.intent.action.TTS_SERVICE"/>
        </intent>
```

- [ ] **Step 2: 构建**

Run: `flutter build apk --debug --dart-define=API_BASE=http://10.0.2.2:8010`
Expected: 生成 `build/app/outputs/flutter-apk/app-debug.apk`（首次会下载 Gradle 与 SDK 平台，耗时较长）。

- [ ] **Step 3: 模拟器运行**（Task 1 判定模拟器可用时）

```powershell
Start-Process E:\dev\android-sdk\emulator\emulator.exe -ArgumentList '-avd','knoact_api35','-no-snapshot'
flutter devices   # 等出现 emulator-5554
flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8010
```

登录 → 首页 → 学习中心浏览正常。模拟器不可用时记录原因，仅以 Step 2 构建成功为验收。

- [ ] **Step 4: Commit**

```bash
git -C D:\workspace\github\KnoAct add student-app/android/app/src/main/AndroidManifest.xml
git -C D:\workspace\github\KnoAct commit -m "feat(student-app): 安卓网络权限与本地 HTTP 后端访问"
```

---

### Task 10: 验收

**由控制者执行。**

- [ ] **Step 1:** `flutter analyze` → `No issues found!`；`flutter test` → 全部通过。
- [ ] **Step 2: Web 同源构建验证** — `flutter build web --release --dart-define=API_BASE=`，再用下面的同源代理（保存为 `$env:TEMP\student_proxy.py`，后台运行 `py $env:TEMP\student_proxy.py`，访问 `http://127.0.0.1:8093`）在浏览器验收：

```python
import http.server
import urllib.error
import urllib.request

ROOT = r"D:\workspace\github\KnoAct\student-app\build\web"
BACKEND = "http://127.0.0.1:8010"
PROXY = ("/api/", "/uploads/", "/health")


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _proxy(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = urllib.request.Request(BACKEND + self.path, data=self.rfile.read(n) if n else None, method=self.command,
                                     headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")})
        try:
            resp = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            resp = e
        data = resp.read()
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith(PROXY):
            return self._proxy()
        return super().do_GET()

    do_POST = _proxy


http.server.ThreadingHTTPServer(("127.0.0.1", 8093), H).serve_forever()
```

  1. 登录（含家长名字被拒、空名字不可提交）；
  2. 首页：问候、积分、第 N 课、今日进度、各学科分组与数量与旧版学生端一致；学科切换；兑换（积分不足提示）；
  3. 学习中心：听力播放、阅读课文、答错收录错题本；
  4. 首页阅读任务 → 自动跳转并在答完后提交 → 回首页显示「等待家长确认」；
  5. 窄屏（手机宽度）底部导航、宽屏左侧导航；
  6. 中文字体正常显示（Flutter Web 需从 Google 字体 CDN 拉取中文回退字体；若无法加载导致方块字，记录为后续问题）；
  7. 「我的」退出后回到登录页。
- [ ] **Step 3: 安卓** — Task 9 的结果。
- [ ] **Step 4: 后端回归** — `backend/` 下 `py -m pytest -q` 全部通过（本子项目不改后端，确认无影响）。
