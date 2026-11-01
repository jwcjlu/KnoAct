# 知学伴 · 学生端（Flutter）

知学伴（KnoAct）的孩子端 App，支持 Web 与 Android，逐步替代旧版 `frontend/`。孩子按名字登录后，可查看今日学习计划与任务、在学习中心完成听力和阅读练习（答错自动收录错题本、任务自动提交给家长确认），并用积分兑换屏幕时间。后端为仓库中的 FastAPI 服务（`/api`）。

## 运行

需要 Flutter 3.47.8+（Dart 3.13.7+）。国内网络先设置 `PUB_HOSTED_URL=https://pub.flutter-io.cn`、`FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn`。

```bash
flutter pub get
flutter run -d chrome                                                      # Web，连本地后端 http://127.0.0.1:8010
flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8010   # 安卓模拟器（必须传 API_BASE）
flutter build web --release --no-web-resources-cdn --dart-define=API_BASE= # 空值：Web 走页面同源，由 nginx 反代 /api
```

`API_BASE`：不传时连 `http://127.0.0.1:8010`；传空值时 Web 使用页面同源；其他值即后端地址。

## 测试

```bash
flutter analyze
flutter test
```

部署（docker）、已知限制等见[仓库根目录 README](../README.md)。
