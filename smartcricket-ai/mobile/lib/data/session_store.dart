import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract class SessionStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> clear();
}

/// The password is never persisted. Tokens use Keychain / encrypted storage.
class SecureSessionStore implements SessionStore {
  SecureSessionStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const tokenKey = 'smartcricket.player.token';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() => _storage.read(key: tokenKey);

  @override
  Future<void> write(String token) =>
      _storage.write(key: tokenKey, value: token);

  @override
  Future<void> clear() => _storage.delete(key: tokenKey);
}
