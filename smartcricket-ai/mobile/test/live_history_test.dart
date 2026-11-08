import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smartcricket_ai/data/api_client.dart';
import 'package:smartcricket_ai/training/live_history_screen.dart';

void main() {
  testWidgets('live history confirms deletion and removes the session card', (
    tester,
  ) async {
    var deleted = false;
    final api = ApiClient(
      baseUrl: 'http://192.168.1.2:8000',
      client: MockClient((request) async {
        if (request.method == 'DELETE') {
          expect(request.url.path, '/api/train/live-sessions/7');
          deleted = true;
          return http.Response('', 204);
        }
        expect(request.url.path, '/api/train/live-sessions');
        return http.Response(
          jsonEncode({
            'sessions': deleted
                ? []
                : [
                    {
                      'id': 7,
                      'title': 'Hook practice',
                      'created_at': '2026-11-08T10:00:00Z',
                      'duration_s': 42,
                      'reps': 2,
                      'completed': false,
                      'best_moment_url': null,
                    },
                  ],
          }),
          200,
        );
      }),
    );
    addTearDown(api.close);
    await tester.pumpWidget(
      MaterialApp(
        home: LiveHistoryScreen(
          client: api,
          token: 'token',
        onBack: (_) {},
          onLogout: () {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Hook practice'), findsOneWidget);
    expect(find.text('No shot image captured'), findsOneWidget);
    await tester.tap(find.text('Delete session'));
    await tester.pumpAndSettle();
    expect(find.textContaining('live-session XP'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Delete session'));
    await tester.pumpAndSettle();
    expect(find.text('No live sessions saved yet.'), findsOneWidget);
  });
}
