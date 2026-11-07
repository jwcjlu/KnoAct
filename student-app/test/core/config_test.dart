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
  test('Web 上空 API_BASE 且 flutter 随机端口：静态资源直连本地后端', () {
    expect(
      resolveApiAssetUrl(
        'uploads/1_p1.png',
        pageUri: Uri.parse('http://localhost:60372/#/reader/view'),
        hasDefine: true,
        defined: '',
        isWeb: true,
      ),
      'http://localhost:8010/uploads/1_p1.png',
    );
  });
  test('Web 上空 API_BASE 且 127.0.0.1 随机端口：静态资源用同 host 连 8010', () {
    expect(
      resolveApiAssetUrl(
        'uploads/1_p1.png',
        pageUri: Uri.parse('http://127.0.0.1:60372/#/reader'),
        hasDefine: true,
        defined: '',
        isWeb: true,
      ),
      'http://127.0.0.1:8010/uploads/1_p1.png',
    );
  });
  test('Web 上空 API_BASE 且已是后端端口：静态资源仍走同源', () {
    expect(
      resolveApiAssetUrl(
        'uploads/1_p1.png',
        pageUri: Uri.parse('http://127.0.0.1:8010/#/reader'),
        hasDefine: true,
        defined: '',
        isWeb: true,
      ),
      'http://127.0.0.1:8010/uploads/1_p1.png',
    );
  });
}
