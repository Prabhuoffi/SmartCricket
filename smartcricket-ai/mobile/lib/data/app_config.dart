import 'package:flutter/foundation.dart';

import 'api_client.dart';

class AppConfig {
  AppConfig._();

  /// The current local demo backend. Override at build time on another network:
  /// --dart-define=API_BASE_URL=https://your-server
  static const localBackendUrl = 'http://10.88.13.145:8002';

  static String get apiBaseUrl =>
      resolve(const String.fromEnvironment('API_BASE_URL'));

  static String resolve(String configured) {
    if (configured.trim().isEmpty ||
        configured.toUpperCase().contains('YOUR_SERVER')) {
      return localBackendUrl;
    }
    try {
      return ApiClient.validateBaseUrl(configured);
    } on ApiException {
      debugPrint(
        'API_BASE_URL "$configured" is not usable; using $localBackendUrl.',
      );
      return localBackendUrl;
    }
  }
}
