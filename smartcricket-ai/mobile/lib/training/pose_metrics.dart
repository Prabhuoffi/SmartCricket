import 'dart:math' as math;

/// A camera-space landmark. Coordinates must use the same units on both axes.
class PosePoint {
  const PosePoint({
    required this.x,
    required this.y,
    required this.confidence,
  });

  final double x;
  final double y;
  final double confidence;

  bool get isVisible =>
      x.isFinite &&
      y.isFinite &&
      confidence.isFinite &&
      confidence >= PoseMetrics.minimumConfidence &&
      confidence <= 1;
}

/// Single-frame 2D measurements, not a shot classifier or technique score.
class PoseMetrics {
  const PoseMetrics._({
    required this.leftKnee,
    required this.rightKnee,
    required this.leftElbow,
    required this.rightElbow,
    required this.shoulderTilt,
    required this.hasBody,
    required this.cue,
    required this.visiblePoints,
  });

  static const minimumConfidence = 0.65;

  factory PoseMetrics.fromPoints(Map<String, PosePoint> points) {
    bool visible(String key) => points[key]?.isVisible ?? false;
    final upperBody = const [
      'leftShoulder',
      'rightShoulder',
      'leftHip',
      'rightHip',
    ].every(visible);
    final lowerBody = const [
      'leftKnee',
      'rightKnee',
      'leftAnkle',
      'rightAnkle',
    ].every(visible);
    return PoseMetrics._(
      leftKnee: _angle(points['leftHip'], points['leftKnee'], points['leftAnkle']),
      rightKnee: _angle(points['rightHip'], points['rightKnee'], points['rightAnkle']),
      leftElbow: _angle(points['leftShoulder'], points['leftElbow'], points['leftWrist']),
      rightElbow: _angle(points['rightShoulder'], points['rightElbow'], points['rightWrist']),
      shoulderTilt: _tilt(points['leftShoulder'], points['rightShoulder']),
      hasBody: upperBody && lowerBody,
      cue: !upperBody
          ? 'Step back until your whole body is visible.'
          : !lowerBody
          ? 'Keep both knees and ankles inside the frame.'
          : 'Body in view. Keep practising at your own pace.',
      visiblePoints: points.values.where((point) => point.isVisible).length,
    );
  }

  final double? leftKnee;
  final double? rightKnee;
  final double? leftElbow;
  final double? rightElbow;
  final double? shoulderTilt;
  final bool hasBody;
  final String cue;
  final int visiblePoints;

  /// Either visible knee can contribute. This does not infer batting handedness.
  double? get mostBentKnee {
    if (leftKnee == null) return rightKnee;
    if (rightKnee == null) return leftKnee;
    return math.min(leftKnee!, rightKnee!);
  }

  static double? _angle(PosePoint? a, PosePoint? b, PosePoint? c) {
    if (a == null || b == null || c == null ||
        !a.isVisible || !b.isVisible || !c.isVisible) {
      return null;
    }
    final ax = a.x - b.x, ay = a.y - b.y;
    final cx = c.x - b.x, cy = c.y - b.y;
    final aLength = math.sqrt(ax * ax + ay * ay);
    final cLength = math.sqrt(cx * cx + cy * cy);
    if (!aLength.isFinite || !cLength.isFinite || aLength < 1e-6 || cLength < 1e-6) {
      return null;
    }
    final cosine = (ax / aLength) * (cx / cLength) + (ay / aLength) * (cy / cLength);
    if (!cosine.isFinite) return null;
    return math.acos(cosine.clamp(-1.0, 1.0)) * 180 / math.pi;
  }

  static double? _tilt(PosePoint? left, PosePoint? right) {
    if (left == null || right == null || !left.isVisible || !right.isVisible) {
      return null;
    }
    final dx = (right.x - left.x).abs(), dy = (right.y - left.y).abs();
    if (!dx.isFinite || !dy.isFinite || (dx < 1e-6 && dy < 1e-6)) return null;
    return math.atan2(dy, dx) * 180 / math.pi;
  }
}

/// Counts the explicit knee-bend drill only; never treat these as batting shots.
///
/// Feed null when body visibility is lost. Pause, camera change, and switching
/// modes must call [clearContinuity] so a rep cannot span separate observations.
class KneeBendCounter {
  static const holdDuration = Duration(milliseconds: 700);
  static const maximumGap = Duration(milliseconds: 400);
  int _reps = 0;
  Duration? _lastFrame;
  Duration? _lowSince;
  bool _held = false;

  int get reps => _reps;

  void update({required double? kneeAngle, required Duration elapsed}) {
    if (kneeAngle == null || !kneeAngle.isFinite ||
        kneeAngle < 0 || kneeAngle > 180 || elapsed.isNegative) {
      clearContinuity();
      return;
    }
    final previous = _lastFrame;
    if (previous != null &&
        (elapsed < previous || elapsed - previous > maximumGap)) {
      clearContinuity();
    }
    _lastFrame = elapsed;

    if (_held) {
      if (kneeAngle > 162) {
        _reps++;
        _held = false;
        _lowSince = null;
      }
      return;
    }
    if (kneeAngle < 150) {
      _lowSince ??= elapsed;
      if (elapsed - _lowSince! >= holdDuration) _held = true;
    } else {
      _lowSince = null;
    }
  }

  void clearContinuity() {
    _lastFrame = null;
    _lowSince = null;
    _held = false;
  }

  void reset() {
    _reps = 0;
    clearContinuity();
  }
}
