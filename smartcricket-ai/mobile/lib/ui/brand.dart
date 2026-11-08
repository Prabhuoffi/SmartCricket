import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'app_theme.dart';

/// The website's logo: the red ball plus "SmartCricket AI" and "Batting analysis & coaching".
class CricketBrand extends StatelessWidget {
  const CricketBrand({super.key, this.light = false, this.compact = false});

  final bool light;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final color = light ? CricketColors.light : CricketColors.ink;
    return Semantics(
      label: 'SmartCricket AI',
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          CricketBall(size: compact ? 32 : 38, glow: true),
          const SizedBox(width: 11),
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'SmartCricket AI',
                    style: TextStyle(
                      color: color,
                      fontSize: compact ? 16 : 18,
                      fontWeight: FontWeight.w800,
                      height: 1.15,
                    ),
                  ),
                  if (!compact)
                    Text(
                      'Batting analysis & coaching',
                      style: TextStyle(
                        color: color.withValues(alpha: .6),
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        letterSpacing: .35,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The cricket ball from the website's SVG (64 x 64 view box). [seamTurns] spins the seam, as on the bowled ball.
class CricketBall extends StatelessWidget {
  const CricketBall({
    super.key,
    this.size = 44,
    this.glow = false,
    this.seamTurns = 0,
  });

  final double size;
  final bool glow;
  final double seamTurns;

  @override
  Widget build(BuildContext context) {
    final ball = CustomPaint(
      size: Size.square(size),
      painter: BallPainter(seamTurns: seamTurns),
    );
    return ExcludeSemantics(
      child: glow
          ? DecoratedBox(
              // drop-shadow(0 4px 10px rgba(200, 16, 46, .5))
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: CricketColors.red.withValues(alpha: .5),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: ball,
            )
          : ball,
    );
  }
}

class BallPainter extends CustomPainter {
  const BallPainter({this.seamTurns = 0});

  final double seamTurns;

  static const _seamColor = Color(0xFFF3E9D2);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 64, size.height / 64);
    const centre = Offset(32, 32);
    const box = Rect.fromLTWH(2, 2, 60, 60);

    // body: radialGradient cx 38% cy 32% r 72%, #f04a62 → #c8102e → #6a0614
    canvas.drawCircle(
      centre,
      30,
      Paint()
        ..shader = const RadialGradient(
          center: Alignment(-.24, -.36),
          radius: .72,
          colors: [Color(0xFFF04A62), Color(0xFFC8102E), Color(0xFF6A0614)],
          stops: [0, .5, 1],
        ).createShader(box),
    );

    // seam: two solid lines and two lines of stitches, optionally spinning about the centre
    canvas.save();
    canvas.clipPath(
      Path()..addOval(Rect.fromCircle(center: centre, radius: 30)),
    );
    if (seamTurns != 0) {
      canvas.translate(32, 32);
      canvas.rotate(seamTurns * 2 * math.pi);
      canvas.translate(-32, -32);
    }
    final solid = Paint()
      ..color = _seamColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.7;
    canvas.drawPath(
      Path()
        ..moveTo(28.6, 2.4)
        ..quadraticBezierTo(22.6, 32, 28.6, 61.6),
      solid,
    );
    canvas.drawPath(
      Path()
        ..moveTo(35.4, 2.4)
        ..quadraticBezierTo(29.4, 32, 35.4, 61.6),
      solid,
    );
    final stitch = Paint()
      ..color = _seamColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round;
    for (final path in [
      Path()
        ..moveTo(24.9, 6)
        ..quadraticBezierTo(18.9, 32, 24.9, 58),
      Path()
        ..moveTo(39.1, 6)
        ..quadraticBezierTo(33.1, 32, 39.1, 58),
    ]) {
      canvas.drawPath(_dashed(path, 1.4, 2.8), stitch);
    }
    canvas.restore();

    // shading: radialGradient cx 70% cy 78% r 60%, black .28 → transparent
    canvas.drawCircle(
      centre,
      30,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(.4, .56),
          radius: .6,
          colors: [
            Colors.black.withValues(alpha: .28),
            Colors.black.withValues(alpha: 0),
          ],
        ).createShader(box),
    );

    // shine: ellipse cx 21 cy 17 rx 9 ry 5, rotated -35°
    canvas.save();
    canvas.translate(21, 17);
    canvas.rotate(-35 * math.pi / 180);
    canvas.drawOval(
      Rect.fromCenter(center: Offset.zero, width: 18, height: 10),
      Paint()..color = Colors.white.withValues(alpha: .28),
    );
    canvas.restore();
    canvas.restore();
  }

  static Path _dashed(Path source, double dash, double gap) {
    final out = Path();
    for (final metric in source.computeMetrics()) {
      for (var d = 0.0; d < metric.length; d += dash + gap) {
        out.addPath(
          metric.extractPath(d, math.min(d + dash, metric.length)),
          Offset.zero,
        );
      }
    }
    return out;
  }

  @override
  bool shouldRepaint(covariant BallPainter oldDelegate) =>
      oldDelegate.seamTurns != seamTurns;
}
