import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smartcricket_ai/data/api_client.dart';

const player = {
  'id': 12,
  'name': 'Test Batter',
  'email': 'batter@example.com',
  'role': 'player',
};

void main() {
  test(
    'checks the SmartCricket health endpoint before credentials are sent',
    () async {
      final api = ApiClient(
        baseUrl: 'http://192.168.1.20:8000',
        client: MockClient((request) async {
          expect(request.method, 'GET');
          expect(request.url.path, '/api/health');
          expect(request.headers.containsKey('Authorization'), isFalse);
          return http.Response('{"status":"ok"}', 200);
        }),
      );
      addTearDown(api.close);
      await api.checkConnection();
    },
  );

  test('rejects a reachable server that is not SmartCricket', () async {
    final api = ApiClient(
      baseUrl: 'http://192.168.1.20:8000',
      client: MockClient((_) async => http.Response('{"status":"other"}', 200)),
    );
    addTearDown(api.close);
    await expectLater(api.checkConnection(), throwsA(isA<ApiException>()));
  });

  test(
    'existing player login verifies identity before returning a session',
    () async {
      final paths = <String>[];
      final api = ApiClient(
        baseUrl: 'https://cricket.example.com/',
        client: MockClient((request) async {
          paths.add(request.url.path);
          expect(request.followRedirects, isFalse);
          if (request.url.path.endsWith('/login')) {
            expect(request.method, 'POST');
            expect(jsonDecode(request.body), {
              'email': 'batter@example.com',
              'password': ' password ',
            });
            return http.Response(
              jsonEncode({
                'token': 'test-token',
                'role': 'player',
                'name': 'Test Batter',
              }),
              200,
            );
          }
          expect(request.headers['Authorization'], 'Bearer test-token');
          return http.Response(jsonEncode(player), 200);
        }),
      );
      addTearDown(api.close);
      final session = await api.login(' batter@example.com ', ' password ');
      expect(session.player.id, 12);
      expect(session.token, 'test-token');
      expect(paths, ['/api/auth/player/login', '/api/auth/me']);
    },
  );

  test('admin response is refused before looking up a profile', () async {
    var calls = 0;
    final api = ApiClient(
      baseUrl: 'http://10.0.2.2:8000',
      client: MockClient((request) async {
        calls++;
        return http.Response('{"token":"admin-token","role":"admin"}', 200);
      }),
    );
    addTearDown(api.close);
    await expectLater(
      api.login('admin@example.com', 'password'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
    );
    expect(calls, 1);
  });

  test('restored token for an admin account is rejected', () async {
    final api = ApiClient(
      baseUrl: 'http://localhost:8000',
      client: MockClient(
        (_) async =>
            http.Response(jsonEncode({...player, 'role': 'admin'}), 200),
      ),
    );
    addTearDown(api.close);
    await expectLater(
      api.me('old-token'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
    );
  });

  test('expired sessions expose 401 for app sign-out handling', () async {
    final api = ApiClient(
      baseUrl: 'http://localhost:8000',
      client: MockClient(
        (_) async => http.Response('{"detail":"expired"}', 401),
      ),
    );
    addTearDown(api.close);
    await expectLater(
      api.trainingToday('expired'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 401)),
    );
  });

  test(
    'connection and malformed response failures have readable messages',
    () async {
      final offline = ApiClient(
        baseUrl: 'http://localhost:8000',
        client: MockClient(
          (_) async => throw http.ClientException('connection refused'),
        ),
      );
      final broken = ApiClient(
        baseUrl: 'http://localhost:8000',
        client: MockClient(
          (_) async => http.Response('<html>wrong server</html>', 200),
        ),
      );
      addTearDown(offline.close);
      addTearDown(broken.close);
      await expectLater(
        offline.me('token'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('Could not reach'),
          ),
        ),
      );
      await expectLater(
        broken.me('token'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('unexpected response'),
          ),
        ),
      );
    },
  );

  test(
    'check-in and save send only expected numbers and explicit user choices',
    () async {
      final requests = <http.Request>[];
      final api = ApiClient(
        baseUrl: 'http://192.168.1.2:8000',
        client: MockClient((request) async {
          requests.add(request);
          return http.Response(
            request.url.path.endsWith('/live-sessions') ? '{"id":42}' : '{}',
            201,
          );
        }),
      );
      addTearDown(api.close);
      await api.checkIn('token', soreness: 'mild', feeling: 3);
      final sessionId = await api.saveLive(
        'token',
        durationSeconds: 42,
        reps: 3,
        stats: {'front_knee_min': 120.5},
      );
      expect(sessionId, 42);
      expect(jsonDecode(requests[0].body), {'soreness': 'mild', 'feeling': 3});
      final saved = jsonDecode(requests[1].body) as Map<String, dynamic>;
      expect(requests[1].url.path, '/api/train/live-sessions');
      expect(saved['duration_s'], 42);
      expect(saved['reps'], 3);
      expect(saved['completed'], false);
      expect(saved.containsKey('drill_id'), false);
      expect(saved['stats'], {'front_knee_min': 120.5});
    },
  );

  test(
    'best moment upload is JPEG multipart and linked to its session',
    () async {
      final api = ApiClient(
        baseUrl: 'http://192.168.1.2:8000',
        client: MockClient((request) async {
          expect(request.method, 'PUT');
          expect(request.url.path, '/api/train/live-sessions/42/best-moment');
          expect(request.headers['Authorization'], 'Bearer token');
          expect(
            request.headers['content-type'],
            startsWith('multipart/form-data'),
          );
          final multipartBody = latin1.decode(request.bodyBytes);
          expect(multipartBody, contains('image/jpeg'));
          expect(multipartBody, contains('live-best-moment.jpg'));
          expect(multipartBody, contains('145.0'));
          return http.Response('{"session_id":42}', 200);
        }),
      );
      addTearDown(api.close);
      await api.saveBestMoment(
        'token',
        42,
        Uint8List.fromList([0xff, 0xd8, 0xff, 0xd9]),
        metric: 'knee',
        value: 145,
      );
    },
  );

  test('unknown shot questions reach the training coach', () async {
    final api = ApiClient(
      baseUrl: 'http://192.168.1.2:8000',
      client: MockClient((request) async {
        expect(request.url.path, '/api/train/chat');
        expect(request.headers['Authorization'], 'Bearer token');
        expect(jsonDecode(request.body)['text'], contains('helicopter shot'));
        return http.Response('{"reply":"Step into the ball."}', 200);
      }),
    );
    addTearDown(api.close);
    expect(
      await api.askCoach('token', 'How do I play a helicopter shot?'),
      'Step into the ball.',
    );
  });

  test(
    'live history loads a private image and deletes image or session',
    () async {
      final calls = <String>[];
      final api = ApiClient(
        baseUrl: 'http://192.168.1.2:8000',
        client: MockClient((request) async {
          expect(request.headers['Authorization'], 'Bearer token');
          expect(request.followRedirects, isFalse);
          calls.add('${request.method} ${request.url.path}');
          if (request.url.path == '/api/train/live-sessions' &&
              request.method == 'GET') {
            return http.Response(
              jsonEncode({
                'sessions': [
                  {
                    'id': 7,
                    'title': 'Hook practice',
                    'created_at': '2026-11-08T10:00:00Z',
                    'duration_s': 42,
                    'reps': 2,
                    'completed': false,
                    'best_moment_url': '/api/train/live-sessions/7/best-moment',
                  },
                ],
              }),
              200,
            );
          }
          if (request.method == 'GET')
            return http.Response.bytes([0xff, 0xd8, 0xff, 0xd9], 200);
          return http.Response('', 204);
        }),
      );
      addTearDown(api.close);
      final history = await api.liveHistory('token');
      expect(history.single.hasImage, isTrue);
      expect(history.single.title, 'Hook practice');
      expect(await api.liveMoment('token', 7), [0xff, 0xd8, 0xff, 0xd9]);
      await api.deleteLiveMoment('token', 7);
      await api.deleteLiveSession('token', 7);
      expect(calls, [
        'GET /api/train/live-sessions',
        'GET /api/train/live-sessions/7/best-moment',
        'DELETE /api/train/live-sessions/7/best-moment',
        'DELETE /api/train/live-sessions/7',
      ]);
    },
  );

  test(
    'public servers require HTTPS and base URLs cannot contain credentials',
    () {
      for (final address in [
        'http://example.com',
        'https://user:password@example.com',
        'https://example.com/api',
        'https://example.com?token=a',
        'file:///tmp/test',
      ]) {
        expect(
          () => ApiClient.validateBaseUrl(address),
          throwsA(isA<ApiException>()),
          reason: address,
        );
      }
      for (final address in [
        'http://10.0.2.2:8000',
        'http://127.0.0.1:8000',
        'http://192.168.1.2:8000',
        'http://172.16.0.1:8000',
        'http://mac.local:8000',
        'https://example.com',
      ]) {
        expect(ApiClient.validateBaseUrl(address), address);
      }
    },
  );
}
