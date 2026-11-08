import 'package:flutter_test/flutter_test.dart';
import 'package:smartcricket_ai/training/pose_metrics.dart';
import 'package:smartcricket_ai/training/shot_motion_tracker.dart';

PosePoint p(double x, double y) => PosePoint(x: x, y: y, confidence: 1);

Map<String, PosePoint> pose(double wristX) => {
  'leftShoulder': p(0, 0),
  'rightShoulder': p(1, 0),
  'leftHip': p(0, 1),
  'rightHip': p(1, 1),
  'leftWrist': p(wristX, .55),
  'rightWrist': p(1 + wristX, .55),
};

void main() {
  test('still stance does not capture, sustained wrist travel does', () {
    final tracker = ShotMotionTracker();
    expect(tracker.update(pose(0), Duration.zero), isNull);
    for (var i = 1; i <= 5; i++) {
      expect(
        tracker.update(pose(.01 * i), Duration(milliseconds: i * 100)),
        isNull,
      );
    }
    expect(
      tracker.update(pose(.25), const Duration(milliseconds: 600)),
      isNull,
    );
    expect(
      tracker.update(pose(.50), const Duration(milliseconds: 700)),
      greaterThan(0),
    );
    expect(
      tracker.update(pose(.70), const Duration(milliseconds: 800)),
      isNull,
      reason: 'a single swing should not trigger repeated still captures',
    );
  });

  test('tracking resets after a long frame gap or lost upper body', () {
    final tracker = ShotMotionTracker();
    tracker.update(pose(0), Duration.zero);
    expect(
      tracker.update(pose(.25), const Duration(milliseconds: 100)),
      isNull,
    );
    expect(
      tracker.update(pose(.50), const Duration(milliseconds: 900)),
      isNull,
    );
    expect(
      tracker.update(pose(.75), const Duration(milliseconds: 1000)),
      isNull,
    );
    final missing = pose(.75)..remove('leftShoulder');
    expect(tracker.update(missing, const Duration(milliseconds: 1100)), isNull);
    expect(
      tracker.update(pose(.75), const Duration(milliseconds: 1200)),
      isNull,
    );
  });
}
