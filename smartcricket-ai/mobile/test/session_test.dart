import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:smartcricket_ai/data/session_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'session store saves only the token and clears it on sign-out',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      final store = SecureSessionStore();
      expect(await store.read(), isNull);
      await store.write('test-player-token');
      expect(await store.read(), 'test-player-token');
      final all = await const FlutterSecureStorage().readAll();
      expect(all.keys, [SecureSessionStore.tokenKey]);
      await store.clear();
      expect(await store.read(), isNull);
    },
  );
}
