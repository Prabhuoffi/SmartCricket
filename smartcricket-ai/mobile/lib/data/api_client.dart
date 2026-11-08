import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class PlayerProfile {
  const PlayerProfile({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
  });

  final int id;
  final String name;
  final String email;
  final String role;

  factory PlayerProfile.fromJson(Map<String, dynamic> json) {
    if (json['role'] != 'player') {
      throw const ApiException(
        'This app is for players. Please use the admin website.',
        statusCode: 403,
      );
    }
    if (json['id'] is! int ||
        json['name'] is! String ||
        (json['name'] as String).trim().isEmpty ||
        json['email'] is! String) {
      throw const ApiException(
        'The server returned an incomplete player account.',
      );
    }
    return PlayerProfile(
      id: json['id'] as int,
      name: json['name'] as String,
      email: json['email'] as String,
      role: json['role'] as String,
    );
  }
}

class PlayerSession {
  const PlayerSession({required this.token, required this.player});

  final String token;
  final PlayerProfile player;
}

class LiveSessionEntry {
  const LiveSessionEntry({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.durationSeconds,
    required this.reps,
    required this.completed,
    required this.hasImage,
  });

  final int id;
  final String title;
  final DateTime createdAt;
  final int durationSeconds;
  final int reps;
  final bool completed;
  final bool hasImage;

  factory LiveSessionEntry.fromJson(Map<String, dynamic> json) =>
      LiveSessionEntry(
        id: json['id'] as int,
        title: json['title'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        durationSeconds: json['duration_s'] as int,
        reps: json['reps'] as int,
        completed: json['completed'] as bool,
        hasImage: json['best_moment_url'] is String,
      );
}

/// Only the existing player and training endpoints are exposed to the app.
class ApiClient {
  ApiClient({required String baseUrl, http.Client? client})
    : baseUrl = validateBaseUrl(baseUrl),
      _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  static String validateBaseUrl(String value) {
    final uri = Uri.tryParse(value.trim());
    if (uri == null ||
        !uri.hasAuthority ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/') ||
        (uri.scheme != 'https' && uri.scheme != 'http')) {
      throw const ApiException(
        'Enter the server address, such as https://cricket.example.com.',
      );
    }
    if (uri.scheme == 'http' && !_isLocalHost(uri.host)) {
      throw const ApiException(
        'Use HTTPS for an internet server. HTTP is only for local development.',
      );
    }
    return uri.replace(path: '').toString();
  }

  static bool _isLocalHost(String host) {
    if (host == 'localhost' ||
        host == '::1' ||
        host == '[::1]' ||
        host.endsWith('.local')) {
      return true;
    }
    final parts = host.split('.').map(int.tryParse).toList();
    if (parts.length != 4 ||
        parts.any((part) => part == null || part < 0 || part > 255)) {
      return false;
    }
    return parts[0] == 127 ||
        parts[0] == 10 ||
        (parts[0] == 192 && parts[1] == 168) ||
        (parts[0] == 172 && parts[1]! >= 16 && parts[1]! <= 31);
  }

  /// Verify that the address points to this backend before sending credentials.
  Future<void> checkConnection() async {
    final health = await _request(
      'GET',
      '/api/health',
      timeout: const Duration(seconds: 6),
    );
    if (health['status'] != 'ok') {
      throw const ApiException(
        'This address does not appear to be a SmartCricket server.',
      );
    }
  }

  Future<PlayerSession> login(String email, String password) async {
    final json = await _request(
      'POST',
      '/api/auth/player/login',
      body: {'email': email.trim(), 'password': password},
    );
    if (json['role'] != 'player') {
      throw const ApiException(
        'This app is for players. Please use the admin website.',
        statusCode: 403,
      );
    }
    final token = json['token'];
    if (token is! String || token.trim().isEmpty) {
      throw const ApiException(
        'The server did not return a valid session. Please try again.',
      );
    }
    // Verify the account before the caller stores the token or opens training.
    return PlayerSession(token: token, player: await me(token));
  }

  Future<PlayerProfile> me(String token) async => PlayerProfile.fromJson(
    await _request('GET', '/api/auth/me', token: token),
  );

  Future<Map<String, dynamic>> trainingToday(String token) =>
      _request('GET', '/api/train/today', token: token);

  Future<Map<String, dynamic>> checkIn(
    String token, {
    required String soreness,
    int? feeling,
  }) => _request(
    'POST',
    '/api/train/checkin',
    token: token,
    body: {'soreness': soreness, 'feeling': ?feeling},
  );

  Future<String> askCoach(String token, String question) async {
    final answer = await _request(
      'POST',
      '/api/train/chat',
      token: token,
      body: {'text': question},
    );
    return answer['reply'] is String
        ? answer['reply'] as String
        : throw const ApiException('The coach did not return an answer.');
  }

  Future<List<LiveSessionEntry>> liveHistory(String token) async {
    final response = await _request(
      'GET',
      '/api/train/live-sessions',
      token: token,
    );
    final rows = response['sessions'];
    if (rows is! List) {
      throw const ApiException('The server returned invalid live history.');
    }
    return rows
        .map((row) => LiveSessionEntry.fromJson(row as Map<String, dynamic>))
        .toList();
  }

  Future<Uint8List> liveMoment(String token, int sessionId) async {
    final request = http.Request(
      'GET',
      Uri.parse('$baseUrl/api/train/live-sessions/$sessionId/best-moment'),
    );
    request.followRedirects = false;
    request.headers['Authorization'] = 'Bearer $token';
    try {
      final response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 20));
      if (response.statusCode != 200) {
        throw ApiException(
          'The captured image is unavailable.',
          statusCode: response.statusCode,
        );
      }
      return response.bodyBytes;
    } on TimeoutException {
      throw const ApiException('The captured image took too long to load.');
    } on http.ClientException {
      throw const ApiException('The captured image could not be loaded.');
    }
  }

  Future<void> deleteLiveMoment(String token, int sessionId) async {
    await _request(
      'DELETE',
      '/api/train/live-sessions/$sessionId/best-moment',
      token: token,
    );
  }

  Future<void> deleteLiveSession(String token, int sessionId) async {
    await _request(
      'DELETE',
      '/api/train/live-sessions/$sessionId',
      token: token,
    );
  }

  Future<int> saveLive(
    String token, {
    required int durationSeconds,
    required int reps,
    required Map<String, dynamic> stats,
  }) async {
    final saved = await _request(
      'POST',
      '/api/train/live-sessions',
      token: token,
      body: {
        'title': 'Mobile live batting practice',
        'duration_s': durationSeconds,
        'reps': reps,
        'hold_s': 0,
        'completed': false,
        'stats': stats,
      },
    );
    final id = saved['id'];
    if (id is! int) {
      throw const ApiException('The server did not return a saved session.');
    }
    return id;
  }

  Future<void> saveBestMoment(
    String token,
    int sessionId,
    Uint8List jpeg, {
    required String metric,
    double? value,
  }) async {
    final request = http.MultipartRequest(
      'PUT',
      Uri.parse('$baseUrl/api/train/live-sessions/$sessionId/best-moment'),
    );
    request.followRedirects = false;
    request.headers['Authorization'] = 'Bearer $token';
    request.fields['metric'] = metric;
    if (value != null) request.fields['value'] = value.toStringAsFixed(1);
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        jpeg,
        filename: 'live-best-moment.jpg',
        contentType: MediaType('image', 'jpeg'),
      ),
    );
    try {
      final response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 30));
      if (response.statusCode != 200) {
        throw ApiException(
          response.statusCode == 413
              ? 'The captured image is too large to save.'
              : 'The session saved, but its image could not be uploaded.',
          statusCode: response.statusCode,
        );
      }
    } on TimeoutException {
      throw const ApiException('The image upload timed out.');
    } on http.ClientException {
      throw const ApiException('The image upload lost its connection.');
    }
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    String? token,
    Map<String, dynamic>? body,
    Duration timeout = const Duration(seconds: 20),
  }) async {
    final request = http.Request(method, Uri.parse('$baseUrl$path'));
    request.headers['Accept'] = 'application/json';
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    final http.Response response;
    try {
      // http.Request does not follow redirects: credentials never follow a
      // deployment redirect to a different host or an insecure endpoint.
      request.followRedirects = false;
      response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(timeout);
    } on TimeoutException {
      throw const ApiException(
        'Could not reach SmartCricket. Check that the backend is running and your phone is on the same Wi-Fi.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Could not reach SmartCricket. Check that the backend is running and your phone is on the same Wi-Fi.',
      );
    }
    Map<String, dynamic>? json;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) json = decoded;
    } on FormatException {
      // HTML proxy errors must not be displayed as API messages.
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final String message;
      if (response.statusCode == 401) {
        message = path.endsWith('/login')
            ? 'Email or password is incorrect.'
            : 'Your session has expired. Please sign in again.';
      } else if (response.statusCode == 403) {
        message = 'This app is for players. Please use the admin website.';
      } else if (response.statusCode == 422) {
        message = 'Please check your details and try again.';
      } else if (response.statusCode == 429) {
        message = 'Too many attempts. Please wait a moment and try again.';
      } else if (response.statusCode == 404 && path.endsWith('/login')) {
        message = 'Update the SmartCricket server to enable player app login.';
      } else if (response.statusCode >= 300 && response.statusCode < 400) {
        message =
            'The server address has changed. Use its final HTTPS address.';
      } else {
        message = 'SmartCricket is unavailable right now. Please try again.';
      }
      throw ApiException(message, statusCode: response.statusCode);
    }
    if (response.statusCode == 204) return {};
    if (json == null) {
      throw const ApiException(
        'The server returned an unexpected response. Please try again.',
      );
    }
    return json;
  }

  void close() => _client.close();
}
