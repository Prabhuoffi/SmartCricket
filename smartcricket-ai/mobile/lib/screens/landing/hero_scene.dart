import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';

import '../../ui/app_theme.dart';
import '../../ui/brand.dart';
import '../../ui/motion.dart';

/// The website hero's bowling scene (.scene in landing.css): the ball is bowled down the pitch, bounces,
/// hits the stumps, the bails fly, sparks and a ring burst out and "Bowled!" is stamped. One 2.8 s loop.
class HeroScene extends StatelessWidget {
  const HeroScene({super.key});

  static const _period = Duration(milliseconds: 2800);

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: AspectRatio(
        aspectRatio: 500 / 600,
        child: LayoutBuilder(builder: (context, box) {
          final w = box.maxWidth;
          return Loop(
            period: _period,
            still: .7,
            builder: (context, t, _) => Stack(
              clipBehavior: Clip.none,
              children: [
                // .scene-wrap::before: soft green glow behind the pitch
                Positioned.fill(
                  child: Padding(
                    padding: EdgeInsets.symmetric(horizontal: w * .06, vertical: w * .1),
                    child: ImageFiltered(
                      imageFilter: ImageFilter.blur(sigmaX: 30, sigmaY: 30),
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(colors: [CricketColors.pitch.withValues(alpha: .5), CricketColors.pitch.withValues(alpha: 0)], stops: const [0, .65]),
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned.fill(child: CustomPaint(painter: _ScenePainter(t, motionOn(context)))),
                _ball(w, t),
                _bowled(w, t),
                // only the first chip on phones, as on the website's mobile layout
                Positioned(left: 0, top: w * 1.2 * .02, child: _FloatChip(phase: 0)),
              ],
            ),
          );
        }),
      ),
    );
  }

  // The ball (30 x 30 in the 500 x 600 view box) moved along the pitch, growing as it comes closer.
  static Widget _ball(double w, double t) {
    const ease = Cubic(.45, .05, .55, .95);
    final along = keyframes(t, const [Kf(0, 0), Kf(.48, .47, ease), Kf(.50, .48, ease), Kf(.86, .92, ease), Kf(1, 1, ease)]);
    final scale = keyframes(t, const [Kf(0, .35), Kf(.48, .72, ease), Kf(.50, .74, ease), Kf(.86, 1.3, ease), Kf(1, 1.45, ease)]);
    final opacity = keyframes(t, const [Kf(0, 0), Kf(.06, 1, ease), Kf(.86, 1, ease), Kf(1, 0, ease)]);
    final bump = t >= .48 && t <= .52 ? 4 * (1 - ((t - .5).abs() / .02)).clamp(0, 1) : 0.0;
    final k = w / 500;
    final y = 92 + 428 * along;
    final size = 30 * k;
    return Positioned(
      left: 250 * k - size / 2,
      top: (y + bump) * k - size / 2,
      width: size,
      height: size,
      child: Opacity(
        opacity: opacity.clamp(0, 1),
        child: Transform.scale(
          scale: scale,
          child: DecoratedBox(
            // drop-shadow(0 0 12px rgba(200, 16, 46, .9))
            decoration: BoxDecoration(shape: BoxShape.circle, boxShadow: [BoxShadow(color: CricketColors.red.withValues(alpha: .9), blurRadius: 12)]),
            child: CricketBall(size: size, seamTurns: (t * 2800 % 400) / 400),
          ),
        ),
      ),
    );
  }

  // "Bowled!" stamp: pops in at 89 to 92%, settles, then lifts away.
  static Widget _bowled(double w, double t) {
    final scale = keyframes(t, const [Kf(0, .4), Kf(.89, .4), Kf(.92, 1.12, kCricketEase), Kf(.95, 1, kCricketEase), Kf(1, 1, kCricketEase)]);
    final opacity = keyframes(t, const [Kf(0, 0), Kf(.89, 0), Kf(.92, 1, kCricketEase), Kf(.99, 1, kCricketEase), Kf(1, 0, kCricketEase)]);
    final lift = keyframes(t, const [Kf(0, 0), Kf(.99, 0), Kf(1, -.1, kCricketEase)]);
    if (opacity <= 0) return const SizedBox.shrink();
    final h = w * 1.2;
    return Positioned(
      left: 0,
      right: 0,
      top: h * .66,
      child: FractionalTranslation(
        translation: Offset(0, -.5 + lift),
        child: Center(
          child: Opacity(
            opacity: opacity.clamp(0, 1),
            child: Transform.rotate(
              angle: -8 * math.pi / 180,
              child: Transform.scale(
                scale: scale,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
                  decoration: BoxDecoration(
                    color: CricketColors.red,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: CricketColors.ink, width: 4),
                    boxShadow: [BoxShadow(color: CricketColors.red.withValues(alpha: .9), blurRadius: 40, offset: const Offset(0, 16), spreadRadius: -10)],
                  ),
                  child: Text('Bowled!', style: CricketFonts.heading(35, color: CricketColors.light).copyWith(letterSpacing: 1.4)),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// .chip-float: a frosted glass chip bobbing up and down every 6 s.
class _FloatChip extends StatelessWidget {
  const _FloatChip({required this.phase});
  final double phase;

  @override
  Widget build(BuildContext context) {
    return Loop(
      period: const Duration(seconds: 6),
      still: 0,
      builder: (context, t, child) {
        final y = -16 * (1 - math.cos(2 * math.pi * ((t + phase) % 1))) / 2;
        return Transform.translate(offset: Offset(0, y), child: child);
      },
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            decoration: BoxDecoration(
              color: CricketColors.night2.withValues(alpha: .55),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: CricketColors.light.withValues(alpha: .16)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 36, height: 36,
                  decoration: BoxDecoration(color: CricketColors.red, borderRadius: BorderRadius.circular(11)),
                  child: const Icon(Icons.accessibility_new_rounded, color: Colors.white, size: 18),
                ),
                const SizedBox(width: 11),
                const Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('33 / 33', style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800, height: 1.1)),
                    Text('body points found', style: TextStyle(color: CricketColors.light, fontSize: 12)),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ScenePainter extends CustomPainter {
  _ScenePainter(this.t, this.motion);

  final double t;
  final bool motion;
  static const _cream = CricketColors.secondary;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 500, size.height / 600);

    // pitch in perspective
    final pitch = Path()..moveTo(208, 80)..lineTo(292, 80)..lineTo(384, 566)..lineTo(116, 566)..close();
    canvas.drawPath(pitch, Paint()..color = _cream.withValues(alpha: .1));
    canvas.drawPath(pitch, Paint()..color = CricketColors.mint.withValues(alpha: .7)..style = PaintingStyle.stroke..strokeWidth = 1.5);
    canvas.drawLine(const Offset(200, 112), const Offset(300, 112), Paint()..color = _cream.withValues(alpha: .6)..strokeWidth = 2);
    canvas.drawLine(const Offset(132, 500), const Offset(368, 500), Paint()..color = _cream.withValues(alpha: .6)..strokeWidth = 3);
    canvas.drawLine(const Offset(146, 478), const Offset(354, 478), Paint()..color = _cream.withValues(alpha: .35)..strokeWidth = 2);

    // far stumps
    final cream = Paint()..color = _cream;
    for (final x in [242.0, 248.5, 255.0]) {
      canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(x, 66, 3, 26), const Radius.circular(1)), cream);
    }
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(240, 63, 20, 3), const Radius.circular(1.5)), cream);

    if (motion) {
      _trail(canvas);
      _bounce(canvas);
    }

    // near stumps, wobbling about their base when hit
    final wobble = keyframes(t, const [Kf(0, 0), Kf(.89, 0), Kf(.92, -8, Curves.easeOut), Kf(.95, 5, Curves.easeOut), Kf(1, 0, Curves.easeOut)]);
    canvas.save();
    canvas.translate(250, 500);
    canvas.rotate(wobble * math.pi / 180);
    canvas.translate(-250, -500);
    for (final x in [222.0, 245.0, 268.0]) {
      canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(x, 408, 10, 92), const Radius.circular(4)), cream);
    }
    canvas.restore();

    // bails fly off
    _bail(canvas, const Rect.fromLTWH(222, 400, 30, 7), -30, -44, -80, -40, -22, -130);
    _bail(canvas, const Rect.fromLTWH(248, 400, 30, 7), 32, -48, 90, 42, -24, 140);

    if (motion) {
      _ring(canvas);
      _sparks(canvas);
    }
    canvas.restore();
  }

  void _trail(Canvas canvas) {
    const ease = Cubic(.45, .05, .55, .95);
    final offset = keyframes(t, const [Kf(0, 60), Kf(.88, -400, ease), Kf(1, -460, ease)]);
    final opacity = keyframes(t, const [Kf(0, 0), Kf(.08, 1, ease), Kf(.88, .9, ease), Kf(1, 0, ease)]);
    final start = (-offset).clamp(0.0, 428.0), end = (-offset + 60).clamp(0.0, 428.0);
    if (end <= start || opacity <= 0) return;
    final p1 = Offset(250, 92 + start), p2 = Offset(250, 92 + end);
    canvas.drawLine(p1, p2, Paint()..color = _cream.withValues(alpha: .9 * opacity)..strokeWidth = 6..strokeCap = StrokeCap.round..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8));
    canvas.drawLine(p1, p2, Paint()..color = _cream.withValues(alpha: opacity)..strokeWidth = 6..strokeCap = StrokeCap.round);
  }

  void _bounce(Canvas canvas) {
    final opacity = keyframes(t, const [Kf(0, 0), Kf(.47, 0), Kf(.50, 1, Curves.easeOut), Kf(.64, 0, Curves.easeOut), Kf(1, 0)]);
    final scale = keyframes(t, const [Kf(0, .2), Kf(.47, .2), Kf(.64, 2.6, Curves.easeOut), Kf(1, 2.6)]);
    if (opacity <= 0) return;
    canvas.drawCircle(const Offset(250, 300), 16 * scale, Paint()..color = _cream.withValues(alpha: opacity)..style = PaintingStyle.stroke..strokeWidth = 3 * scale);
  }

  void _bail(Canvas canvas, Rect rect, double x1, double y1, double r1, double x2, double y2, double r2) {
    final dx = keyframes(t, [const Kf(0, 0), const Kf(.88, 0), Kf(.96, x1, kCricketEase), Kf(1, x2, kCricketEase)]);
    final dy = keyframes(t, [const Kf(0, 0), const Kf(.88, 0), Kf(.96, y1, kCricketEase), Kf(1, y2, kCricketEase)]);
    final rot = keyframes(t, [const Kf(0, 0), const Kf(.88, 0), Kf(.96, r1, kCricketEase), Kf(1, r2, kCricketEase)]);
    final opacity = keyframes(t, const [Kf(0, 1), Kf(.96, 1), Kf(1, 0, kCricketEase)]);
    canvas.save();
    canvas.translate(rect.center.dx + dx, rect.center.dy + dy);
    canvas.rotate(rot * math.pi / 180);
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromCenter(center: Offset.zero, width: rect.width, height: rect.height), const Radius.circular(3.5)),
      Paint()..color = _cream.withValues(alpha: opacity.clamp(0, 1)),
    );
    canvas.restore();
  }

  void _ring(Canvas canvas) {
    final opacity = keyframes(t, const [Kf(0, 0), Kf(.88, 0), Kf(.91, 1, Curves.easeOut), Kf(1, 0, Curves.easeOut)]);
    final scale = keyframes(t, const [Kf(0, .3), Kf(.88, .3), Kf(1, 2.8, Curves.easeOut)]);
    if (opacity <= 0) return;
    canvas.drawCircle(const Offset(250, 440), 40 * scale, Paint()..color = _cream.withValues(alpha: opacity)..style = PaintingStyle.stroke..strokeWidth = 4 * scale);
  }

  // ten sparks fanning out from the stumps: a 14-long dash that slides 26 along each 40-long line
  void _sparks(Canvas canvas) {
    if (t < .88) return;
    final show = t < .90 ? Curves.easeOut.transform((t - .88) / .02) : 1.0;
    final slide = t < .90 ? 0.0 : 26 * Curves.easeOut.transform((t - .90) / .10);
    final opacity = t < .90 ? show : 1 - Curves.easeOut.transform((t - .90) / .10);
    final paint = Paint()..color = _cream.withValues(alpha: opacity.clamp(0, 1))..strokeWidth = 3..strokeCap = StrokeCap.round;
    for (var k = 0; k < 10; k++) {
      final a = (-160 + k * 16) * math.pi / 180;
      final dir = Offset(math.cos(a), math.sin(a));
      final from = const Offset(250, 430) + dir * (30 + slide);
      final to = const Offset(250, 430) + dir * (30 + slide + 14 * show);
      canvas.drawLine(from, to, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _ScenePainter old) => old.t != t || old.motion != motion;
}
