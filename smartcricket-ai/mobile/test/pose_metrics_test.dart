import 'package:flutter_test/flutter_test.dart';
import 'package:smartcricket_ai/training/pose_metrics.dart';

PosePoint point(double x, double y, [double confidence = 1]) =>
    PosePoint(x: x, y: y, confidence: confidence);

Map<String, PosePoint> body() => {
  'leftShoulder': point(10, 10),
  'rightShoulder': point(30, 10),
  'leftElbow': point(10, 20),
  'leftWrist': point(20, 20),
  'rightElbow': point(30, 20),
  'rightWrist': point(30, 30),
  'leftHip': point(10, 30),
  'rightHip': point(30, 30),
  'leftKnee': point(10, 40),
  'rightKnee': point(30, 40),
  'leftAnkle': point(20, 40),
  'rightAnkle': point(30, 50),
};

void feed(KneeBendCounter counter, int milliseconds, double? knee) =>
    counter.update(kneeAngle: knee, elapsed: Duration(milliseconds: milliseconds));

void held(KneeBendCounter counter, int start) {
  for (final offset in [0, 200, 400, 700]) {
    feed(counter, start + offset, 140);
  }
}

void main() {
  group('PoseMetrics', () {
    test('measures knees, elbows and shoulder tilt in camera coordinates', () {
      final metrics = PoseMetrics.fromPoints(body());
      expect(metrics.leftKnee, closeTo(90, 1e-9));
      expect(metrics.rightKnee, closeTo(180, 1e-9));
      expect(metrics.leftElbow, closeTo(90, 1e-9));
      expect(metrics.rightElbow, closeTo(180, 1e-9));
      expect(metrics.mostBentKnee, closeTo(90, 1e-9));
      expect(metrics.shoulderTilt, closeTo(0, 1e-9));
      expect(metrics.hasBody, isTrue);
      expect(metrics.visiblePoints, 12);
    });

    test('visibility threshold excludes unreliable joints without inventing zero', () {
      final points = body()..['leftKnee'] = point(10, 40, 0.64);
      var metrics = PoseMetrics.fromPoints(points);
      expect(metrics.leftKnee, isNull);
      expect(metrics.mostBentKnee, closeTo(180, 1e-9));
      expect(metrics.hasBody, isFalse);
      expect(metrics.visiblePoints, 11);
      expect(metrics.cue, contains('knees and ankles'));
      points['leftKnee'] = point(10, 40, 0.65);
      metrics = PoseMetrics.fromPoints(points);
      expect(metrics.leftKnee, closeTo(90, 1e-9));
      expect(metrics.hasBody, isTrue);
    });

    test('empty, degenerate and non-finite landmarks remain unavailable', () {
      final empty = PoseMetrics.fromPoints({});
      expect(empty.mostBentKnee, isNull);
      expect(empty.shoulderTilt, isNull);
      expect(empty.hasBody, isFalse);
      expect(empty.visiblePoints, 0);
      expect(empty.cue, contains('whole body'));
      final points = body()
        ..['leftAnkle'] = point(10, 40)
        ..['rightHip'] = point(double.nan, 30)
        ..['leftShoulder'] = point(30, 10)
        ..['rightWrist'] = point(30, 30, double.infinity);
      final metrics = PoseMetrics.fromPoints(points);
      expect(metrics.leftKnee, isNull);
      expect(metrics.rightKnee, isNull);
      expect(metrics.rightElbow, isNull);
      expect(metrics.shoulderTilt, isNull);
      expect(metrics.hasBody, isFalse);
    });

    test('shoulder tilt is mirrored consistently and angles survive translation', () {
      final points = body()..['rightShoulder'] = point(30, 30);
      final mirrored = points.map((key, value) => MapEntry(key,
          point(100 - value.x, value.y + 37, value.confidence)));
      final first = PoseMetrics.fromPoints(points);
      final second = PoseMetrics.fromPoints(mirrored);
      expect(first.shoulderTilt, closeTo(45, 1e-9));
      expect(second.shoulderTilt, closeTo(first.shoulderTilt!, 1e-9));
      expect(second.leftKnee, closeTo(first.leftKnee!, 1e-9));
    });
  });

  group('KneeBendCounter', () {
    test('requires a held bend and full return; standing cannot add reps', () {
      final counter = KneeBendCounter();
      feed(counter, 0, 175);
      held(counter, 100);
      expect(counter.reps, 0);
      feed(counter, 900, 162);
      expect(counter.reps, 0);
      feed(counter, 1000, 163);
      expect(counter.reps, 1);
      feed(counter, 1100, 180);
      feed(counter, 1200, 170);
      expect(counter.reps, 1);
      held(counter, 1300);
      feed(counter, 2100, 170);
      expect(counter.reps, 2);
    });

    test('brief bends and threshold noise cannot complete the hold', () {
      final counter = KneeBendCounter();
      feed(counter, 0, 140);
      feed(counter, 300, 140);
      feed(counter, 600, 150);
      feed(counter, 700, 140);
      feed(counter, 1000, 149);
      feed(counter, 1300, 170);
      expect(counter.reps, 0);
    });

    test('missing detections and long frame gaps break a pending rep', () {
      final counter = KneeBendCounter();
      held(counter, 0);
      feed(counter, 800, null);
      feed(counter, 900, 175);
      expect(counter.reps, 0);
      held(counter, 1000);
      feed(counter, 2101, 175);
      expect(counter.reps, 0);
      feed(counter, 2200, 140);
      feed(counter, 3000, 140);
      feed(counter, 3100, 175);
      expect(counter.reps, 0);
    });

    test('a backwards clock and invalid angles cannot finish an armed rep', () {
      final counter = KneeBendCounter();
      held(counter, 1000);
      feed(counter, 1600, 175);
      expect(counter.reps, 0);
      for (final invalid in [double.nan, double.infinity, -1.0, 181.0]) {
        held(counter, 2000);
        feed(counter, 2800, invalid);
        feed(counter, 2900, 175);
        expect(counter.reps, 0);
      }
    });

    test('pause clears continuity, while reset also clears completed reps', () {
      final counter = KneeBendCounter();
      held(counter, 0);
      feed(counter, 800, 175);
      held(counter, 900);
      counter.clearContinuity();
      feed(counter, 1700, 175);
      expect(counter.reps, 1);
      counter.reset();
      expect(counter.reps, 0);
      feed(counter, 1800, 175);
      expect(counter.reps, 0);
    });
  });
}
