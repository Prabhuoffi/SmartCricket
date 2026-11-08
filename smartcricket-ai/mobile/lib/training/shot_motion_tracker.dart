import 'dart:math' as math;

import 'pose_metrics.dart';

/// A likely batting action: sustained wrist travel relative to the torso.
/// This chooses a frame to keep; it does not classify a cricket shot or grade form.
class ShotMotionTracker {
  Duration? _lastAt;
  Map<String, _Vector> _previous = const {};
  int _movingFrames = 0;
  Duration? _lastCandidateAt;

  void reset() {
    _lastAt = null;
    _previous = const {};
    _movingFrames = 0;
    _lastCandidateAt = null;
  }

  double? update(Map<String, PosePoint> points, Duration elapsed) {
    final leftShoulder = points['leftShoulder'];
    final rightShoulder = points['rightShoulder'];
    final leftHip = points['leftHip'];
    final rightHip = points['rightHip'];
    if (leftShoulder == null ||
        rightShoulder == null ||
        leftHip == null ||
        rightHip == null ||
        !leftShoulder.isVisible ||
        !rightShoulder.isVisible ||
        !leftHip.isVisible ||
        !rightHip.isVisible) {
      reset();
      return null;
    }
    final shoulderCenter = _Vector(
      (leftShoulder.x + rightShoulder.x) / 2,
      (leftShoulder.y + rightShoulder.y) / 2,
    );
    final hipCenter = _Vector(
      (leftHip.x + rightHip.x) / 2,
      (leftHip.y + rightHip.y) / 2,
    );
    final torso = shoulderCenter.distanceTo(hipCenter);
    if (!torso.isFinite || torso < 1e-5) {
      reset();
      return null;
    }
    final current = <String, _Vector>{};
    for (final side in ['left', 'right']) {
      final wrist = points['${side}Wrist'];
      final shoulder = points['${side}Shoulder'];
      if (wrist?.isVisible == true && shoulder?.isVisible == true) {
        current[side] = _Vector(
          (wrist!.x - shoulder!.x) / torso,
          (wrist.y - shoulder.y) / torso,
        );
      }
    }
    if (current.isEmpty) {
      reset();
      return null;
    }
    final lastAt = _lastAt;
    final previous = _previous;
    _lastAt = elapsed;
    _previous = current;
    if (lastAt == null) return null;
    final seconds = (elapsed - lastAt).inMicroseconds / 1000000;
    if (seconds < .04 || seconds > .5) {
      _movingFrames = 0;
      return null;
    }
    var speed = 0.0;
    for (final entry in current.entries) {
      final old = previous[entry.key];
      if (old != null) {
        speed = math.max(speed, entry.value.distanceTo(old) / seconds);
      }
    }
    _movingFrames = speed >= .55
        ? _movingFrames + 1
        : math.max(0, _movingFrames - 1);
    final extension = current.values.map((v) => v.length).reduce(math.max);
    if (_movingFrames < 2 || extension < .45) return null;
    if (_lastCandidateAt != null &&
        elapsed - _lastCandidateAt! < const Duration(seconds: 1)) {
      return null;
    }
    _lastCandidateAt = elapsed;
    final visible = points.values.where((point) => point.isVisible).length;
    return visible * 4 + math.min(speed, 4) * 8 + math.min(extension, 2) * 6;
  }
}

class _Vector {
  const _Vector(this.x, this.y);
  final double x;
  final double y;
  double get length => math.sqrt(x * x + y * y);
  double distanceTo(_Vector other) =>
      math.sqrt(math.pow(x - other.x, 2) + math.pow(y - other.y, 2));
}
