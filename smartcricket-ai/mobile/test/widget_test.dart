import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smartcricket_ai/data/api_client.dart';
import 'package:smartcricket_ai/data/session_store.dart';
import 'package:smartcricket_ai/screens/landing_screen.dart';
import 'package:smartcricket_ai/screens/login_screen.dart';
import 'package:smartcricket_ai/training/checkin_screen.dart';
import 'package:smartcricket_ai/training/session_report.dart';
import 'package:smartcricket_ai/training/session_summary_screen.dart';
import 'package:smartcricket_ai/ui/app_theme.dart';

Widget _app(
  Widget child, {
  bool reduceMotion = false,
  Size size = const Size(412, 915),
}) => MaterialApp(
  theme: SmartCricketTheme.light(),
  home: MediaQuery(
    data: MediaQueryData(size: size, disableAnimations: reduceMotion),
    child: child,
  ),
);

/// Load the real brand fonts so text is measured as on a phone (tests otherwise use a square block font).
Future<void> _loadFonts() async {
  Future<ByteData> read(String path) async =>
      ByteData.sublistView(await File(path).readAsBytes());
  await (FontLoader(
    'Anton',
  )..addFont(read('assets/fonts/Anton-Regular.ttf'))).load();
  final jakarta = FontLoader('PlusJakartaSans');
  for (final w in [400, 500, 600, 700, 800]) {
    jakarta.addFont(read('assets/fonts/PlusJakartaSans-$w.ttf'));
  }
  await jakarta.load();
}

void main() {
  setUpAll(_loadFonts);

  testWidgets(
    'coach check-in routes rest and live practice correctly on a phone',
    (tester) async {
      tester.view.physicalSize = const Size(722, 1600);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      var openedLive = 0;
      final api = ApiClient(
        baseUrl: 'http://192.168.1.20:8000',
        client: MockClient((request) async {
          expect(request.url.path, '/api/train/checkin');
          final rest = request.body.contains('"soreness":"stop"');
          return http.Response('{"rest_day":$rest}', 200);
        }),
      );
      addTearDown(api.close);
      await tester.pumpWidget(
        _app(
          CheckInScreen(
            player: const PlayerProfile(
              id: 1,
              name: 'Demo Player',
              email: 'demo@example.com',
              role: 'player',
            ),
            token: 'test-token',
            client: api,
            store: _TestStore(),
            onReady: () => openedLive++,
            onLogout: () {},
          ),
          size: const Size(361, 800),
        ),
      );

      expect(find.text('LIVE ANALYSIS'), findsOneWidget);
      expect(find.text('Quick coach check-in'), findsOneWidget);
      await tester.tap(find.byKey(const Key('soreness-stop')));
      await tester.pump();
      expect(find.text('Save recovery check-in'), findsOneWidget);
      await tester.tap(find.byKey(const Key('checkin-continue')));
      await tester.pumpAndSettle();
      expect(find.text('Recovery comes first'), findsOneWidget);
      expect(openedLive, 0);

      await tester.tap(find.text('Update check-in'));
      await tester.pump();
      await tester.tap(find.byKey(const Key('soreness-none')));
      await tester.tap(find.byKey(const Key('checkin-continue')));
      await tester.pumpAndSettle();
      expect(openedLive, 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('session recap shows measured results and honest save status', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(722, 1600);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      _app(
        SessionSummaryScreen(
          player: const PlayerProfile(
            id: 1,
            name: 'Demo Player',
            email: 'demo@example.com',
            role: 'player',
          ),
          report: const SessionReport(
            durationSeconds: 83,
            reps: 4,
            saved: false,
            leftKnee: 149,
            shoulderTilt: 6,
            saveError: 'Could not save this session.',
          ),
          onPractiseAgain: () {},
          onLogout: () {},
        ),
        size: const Size(361, 800),
      ),
    );
    expect(find.text('SESSION ENDED'), findsOneWidget);
    expect(find.text('1:23'), findsOneWidget);
    expect(find.text('4'), findsOneWidget);
    expect(find.text('Could not save this session.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('saved session recap shows its automatic best moment', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(722, 1600);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final image = File('assets/img/demo-batter.jpg').readAsBytesSync();
    await tester.pumpWidget(
      _app(
        SessionSummaryScreen(
          player: const PlayerProfile(
            id: 1,
            name: 'Demo Player',
            email: 'demo@example.com',
            role: 'player',
          ),
          report: SessionReport(
            durationSeconds: 45,
            reps: 3,
            saved: true,
            bestMomentBytes: image,
            momentSaved: true,
          ),
          onPractiseAgain: () {},
          onLogout: () {},
        ),
        size: const Size(361, 800),
      ),
    );
    await tester.pump();
    expect(find.text('Your tracked shot moment'), findsOneWidget);
    expect(find.text('SHOT'), findsOneWidget);
    expect(find.byType(Image), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('recap retries an image upload without saving a second session', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(722, 1600);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final image = File('assets/img/demo-batter.jpg').readAsBytesSync();
    var uploads = 0;
    final api = ApiClient(
      baseUrl: 'http://192.168.1.2:8000',
      client: MockClient((request) async {
        expect(request.method, 'PUT');
        expect(request.url.path, '/api/train/live-sessions/42/best-moment');
        uploads++;
        return http.Response('{"session_id":42}', 200);
      }),
    );
    addTearDown(api.close);
    await tester.pumpWidget(
      _app(
        SessionSummaryScreen(
          player: const PlayerProfile(
            id: 1,
            name: 'Demo Player',
            email: 'demo@example.com',
            role: 'player',
          ),
          report: SessionReport(
            durationSeconds: 45,
            reps: 3,
            saved: true,
            sessionId: 42,
            bestMomentBytes: image,
            momentSaveError: 'The image upload lost its connection.',
          ),
          client: api,
          token: 'test-token',
          onPractiseAgain: () {},
          onLogout: () {},
        ),
        size: const Size(361, 800),
      ),
    );
    await tester.ensureVisible(find.text('Retry image save'));
    await tester.tap(find.text('Retry image save'));
    await tester.pump();
    expect(uploads, 1);
    expect(
      find.text(
        'Captured during clear arm movement and saved with this session.',
      ),
      findsOneWidget,
    );
    expect(find.text('Retry image save'), findsNothing);
  });

  testWidgets('phone login submits credentials without server setup', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(722, 1600);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final attempts = <String>[];
    await tester.pumpWidget(
      _app(
        LoginScreen(
          onBack: () {},
          onLogin: (email, password) async => attempts.add(email),
        ),
        size: const Size(361, 800),
      ),
    );

    expect(find.text('WELCOME BACK'), findsOneWidget);
    expect(find.byKey(const Key('login-server')), findsNothing);
    expect(find.text('Set your server address'), findsNothing);
    await tester.enterText(
      find.byKey(const Key('login-email')),
      'demo@example.com',
    );
    await tester.enterText(find.byKey(const Key('login-password')), 'password');
    await tester.ensureVisible(find.byKey(const Key('login-submit')));
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pump();
    expect(attempts, ['demo@example.com']);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'intro plays, then the landing page shows the website brand and opens login',
    (tester) async {
      var opened = 0;
      tester.view.physicalSize = const Size(412, 915) * 3;
      tester.view.devicePixelRatio = 3;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(_app(LandingScreen(onLogin: () => opened++)));

      expect(find.text('BATTING ANALYSIS & COACHING'), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 2100)); // intro stage
      await tester.pump(const Duration(milliseconds: 1000)); // split open
      expect(find.text('BATTING ANALYSIS & COACHING'), findsNothing);

      expect(find.text('SmartCricket AI'), findsWidgets);
      expect(find.text('Batting analysis & coaching'), findsWidgets);
      expect(
        find.bySemanticsLabel('See every stroke. Understand every angle.'),
        findsOneWidget,
      );

      await tester.tap(find.byKey(const Key('landing-login')));
      expect(opened, 1);
    },
  );

  testWidgets(
    'reduced motion skips the intro and every section can be scrolled to',
    (tester) async {
      tester.view.physicalSize = const Size(412, 915) * 3;
      tester.view.devicePixelRatio = 3;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _app(LandingScreen(onLogin: () {}), reduceMotion: true),
      );
      await tester.pump();
      await tester.pump();
      expect(find.text('BATTING ANALYSIS & COACHING'), findsNothing);

      final scroll = find.byKey(const Key('landing-scroll'));
      for (final text in ['THREE STEPS', 'LIVE DEMO', 'QUESTIONS']) {
        await tester.scrollUntilVisible(
          find.text(text),
          500,
          scrollable: find
              .descendant(of: scroll, matching: find.byType(Scrollable))
              .first,
        );
        expect(find.text(text), findsOneWidget);
      }
      // centre the question on screen, clear of the floating nav bar
      Scrollable.ensureVisible(
        tester.element(find.text('Do I need special equipment?')),
        alignment: .5,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Do I need special equipment?'));
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.textContaining('A phone camera is enough'), findsOneWidget);
    },
  );

  testWidgets(
    'narrow phone keeps the landing navigation clear while scrolling',
    (tester) async {
      tester.view.physicalSize = const Size(722, 1600);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _app(
          LandingScreen(onLogin: () {}, showIntro: false),
          reduceMotion: true,
          size: const Size(361, 800),
        ),
      );
      await tester.pump();

      expect(find.byKey(const Key('landing-login')), findsOneWidget);
      expect(find.text('Get started'), findsNothing);
      final scroll = find.byKey(const Key('landing-scroll'));
      await tester.scrollUntilVisible(
        find.text('Live mirror'),
        450,
        scrollable: find
            .descendant(of: scroll, matching: find.byType(Scrollable))
            .first,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(seconds: 2));
    },
  );

  testWidgets(
    '"See it in action" scrolls the live demo into view below the nav bar',
    (tester) async {
      tester.view.physicalSize = const Size(412, 915) * 3;
      tester.view.devicePixelRatio = 3;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _app(
          LandingScreen(onLogin: () {}, showIntro: false),
          reduceMotion: true,
        ),
      );
      await tester.pump();
      await tester.tap(find.text('See it in action'));
      await tester.pump();
      final top = tester.getTopLeft(find.byType(Image)).dy;
      expect(top, greaterThan(64));
      expect(top, lessThan(915 / 2));
      await tester.pump(
        const Duration(seconds: 2),
      ); // let the heading underline timers finish
    },
  );
}

class _TestStore implements SessionStore {
  @override
  Future<void> clear() async {}

  @override
  Future<String?> read() async => null;

  @override
  Future<void> write(String token) async {}
}
