import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'data/api_client.dart';
import 'data/app_config.dart';
import 'data/session_store.dart';
import 'screens/landing_screen.dart';
import 'screens/login_screen.dart';
import 'training/checkin_screen.dart';
import 'training/live_training_screen.dart';
import 'training/live_history_screen.dart';
import 'training/session_report.dart';
import 'training/session_summary_screen.dart';
import 'ui/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  runApp(const SmartCricketApp());
}

class SmartCricketApp extends StatelessWidget {
  const SmartCricketApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SmartCricket AI',
      theme: SmartCricketTheme.light(),
      debugShowCheckedModeBanner: false,
      home: const _AppRoot(),
    );
  }
}

// ── Navigation state machine ──────────────────────────────────────────────────

enum _Screen { landing, login, checkIn, liveTraining, summary, history }

class _AppRoot extends StatefulWidget {
  const _AppRoot();

  @override
  State<_AppRoot> createState() => _AppRootState();
}

class _AppRootState extends State<_AppRoot> {
  _Screen _screen = _Screen.landing;
  bool _introPlayed = false;
  String? _loginNotice;

  // ── ApiClient is created lazily on first login — NEVER at class-init time.
  // A bad URL cannot crash the app before any screen appears. ──────────────
  ApiClient? _client;
  final SessionStore _store = SecureSessionStore();

  PlayerSession? _session;
  SessionReport? _report;
  _Screen _historyReturn = _Screen.checkIn;
  final String _serverUrl = AppConfig.apiBaseUrl;

  @override
  void dispose() {
    _client?.close();
    super.dispose();
  }

  Future<void> _handleLogin(String email, String password) async {
    _client ??= ApiClient(baseUrl: _serverUrl);

    // Check the server before sending a password, so a wrong LAN address gets
    // a clear connection error rather than a long login timeout.
    await _client!.checkConnection();
    final session = await _client!.login(email, password);
    await _store.write(session.token);
    setState(() {
      _session = session;
      _screen = _Screen.checkIn;
    });
  }

  void _logout() {
    _store.clear();
    setState(() {
      _session = null;
      _screen = _Screen.landing;
      _loginNotice = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 280),
      child: _buildScreen(),
    );
  }

  Widget _buildScreen() {
    switch (_screen) {
      case _Screen.landing:
        final intro = !_introPlayed;
        _introPlayed = true;
        return LandingScreen(
          key: const ValueKey('landing'),
          showIntro: intro,
          onLogin: () => setState(() {
            _screen = _Screen.login;
            _loginNotice = null;
          }),
        );

      case _Screen.login:
        return LoginScreen(
          key: const ValueKey('login'),
          notice: _loginNotice,
          onLogin: _handleLogin,
          onBack: () => setState(() => _screen = _Screen.landing),
        );

      case _Screen.checkIn:
        final session = _session;
        if (session == null) {
          return LandingScreen(
            key: const ValueKey('landing-fb'),
            showIntro: false,
            onLogin: () => setState(() => _screen = _Screen.login),
          );
        }
        return CheckInScreen(
          key: const ValueKey('checkin'),
          player: session.player,
          token: session.token,
          client: _client!,
          store: _store,
          onReady: () => setState(() => _screen = _Screen.liveTraining),
          onHistory: () => setState(() {
            _historyReturn = _Screen.checkIn;
            _screen = _Screen.history;
          }),
          onLogout: _logout,
        );

      case _Screen.liveTraining:
        final session = _session;
        if (session == null) {
          _logout();
          return LandingScreen(
            key: const ValueKey('landing-fb2'),
            showIntro: false,
            onLogin: () => setState(() => _screen = _Screen.login),
          );
        }
        return LiveTrainingScreen(
          key: const ValueKey('live'),
          player: session.player,
          token: session.token,
          client: _client!,
          onFinish: (report) => setState(() {
            _report = report;
            _screen = _Screen.summary;
          }),
          onBack: () => setState(() => _screen = _Screen.checkIn),
          onLogout: _logout,
        );

      case _Screen.summary:
        final session = _session;
        return SessionSummaryScreen(
          key: const ValueKey('summary'),
          player:
              session?.player ??
              const PlayerProfile(
                id: 0,
                name: 'Player',
                email: '',
                role: 'player',
              ),
          report: _report,
          client: _client,
          token: session?.token,
          onPractiseAgain: () => setState(() {
            _report = null;
            _screen = _Screen.checkIn;
          }),
          onHistory: () => setState(() {
            _historyReturn = _Screen.summary;
            _screen = _Screen.history;
          }),
          onLogout: _logout,
        );

      case _Screen.history:
        final session = _session;
        if (session == null) {
          _logout();
          return LandingScreen(
            key: const ValueKey('landing-fb3'),
            showIntro: false,
            onLogin: () => setState(() => _screen = _Screen.login),
          );
        }
        return LiveHistoryScreen(
          key: const ValueKey('history'),
          client: _client!,
          token: session.token,
          onBack: (changed) => setState(() => _screen = changed ? _Screen.checkIn : _historyReturn),
          onLogout: _logout,
        );
    }
  }
}
