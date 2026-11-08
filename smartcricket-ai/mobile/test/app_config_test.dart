import 'package:flutter_test/flutter_test.dart';
import 'package:smartcricket_ai/data/app_config.dart';

void main() {
  test('uses the local backend when no build-time URL is provided', () {
    expect(AppConfig.resolve(''), AppConfig.localBackendUrl);
  });

  test('placeholder and unusable addresses fall back to local backend', () {
    expect(
      AppConfig.resolve('http://YOUR_SERVER:8000'),
      AppConfig.localBackendUrl,
    );
    expect(
      AppConfig.resolve('http://cricket.example.com'),
      AppConfig.localBackendUrl,
    );
    expect(AppConfig.resolve('not a url'), AppConfig.localBackendUrl);
  });

  test('a valid configured address is kept', () {
    expect(
      AppConfig.resolve('https://cricket.example.com'),
      'https://cricket.example.com',
    );
    expect(
      AppConfig.resolve('http://192.168.1.20:8000'),
      'http://192.168.1.20:8000',
    );
  });
}
