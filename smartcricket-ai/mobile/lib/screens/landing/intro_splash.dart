import 'dart:ui';

import 'package:flutter/material.dart';

import '../../ui/app_theme.dart';
import '../../ui/brand.dart';
import '../../ui/motion.dart';

/// The website's intro (landing-fx.js, section 1): the ball drops and bounces twice with shockwaves,
/// The full app name appears after the ball lands, then the screen splits open. Tap to skip.
class IntroSplash extends StatefulWidget {
  const IntroSplash({super.key, required this.onDone});

  final VoidCallback onDone;

  @override
  State<IntroSplash> createState() => _IntroSplashState();
}

class _IntroSplashState extends State<IntroSplash> with TickerProviderStateMixin {
  static const _stageMs = 2050;
  late final AnimationController _stage = AnimationController(vsync: this, duration: const Duration(milliseconds: _stageMs));
  late final AnimationController _out = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
  bool _finishing = false;

  @override
  void initState() {
    super.initState();
    _stage.forward().whenComplete(_finish);
    _out.addStatusListener((s) {
      if (s == AnimationStatus.completed) widget.onDone();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!motionOn(context)) WidgetsBinding.instance.addPostFrameCallback((_) => widget.onDone());
  }

  void _finish() {
    if (_finishing || !mounted) return;
    _finishing = true;
    _out.forward();
  }

  @override
  void dispose() {
    _stage.dispose();
    _out.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: _finish,
      child: Semantics(
        label: 'SmartCricket AI. Tap to skip the intro.',
        button: true,
        child: AnimatedBuilder(
          animation: Listenable.merge([_stage, _out]),
          builder: (context, _) {
            final size = MediaQuery.sizeOf(context);
            final ms = _stage.value * _stageMs;
            final split = const Cubic(.77, 0, .18, 1).transform(_out.value);
            final stageFade = 1 - Curves.ease.transform((_out.value / .39).clamp(0, 1));
            final stageScale = 1 + .08 * kCricketEase.transform((_out.value / .67).clamp(0, 1));
            return Stack(
              children: [
                // the two halves that slide away
                Positioned(
                  left: 0, right: 0, top: 0, height: size.height * .505,
                  child: Transform.translate(
                    offset: Offset(0, -size.height * .505 * 1.01 * split),
                    child: const DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF041D12), CricketColors.night]))),
                  ),
                ),
                Positioned(
                  left: 0, right: 0, bottom: 0, height: size.height * .505,
                  child: Transform.translate(
                    offset: Offset(0, size.height * .505 * 1.01 * split),
                    child: DecoratedBox(
                      decoration: const BoxDecoration(gradient: LinearGradient(begin: Alignment.bottomCenter, end: Alignment.topCenter, colors: [Color(0xFF041D12), CricketColors.night])),
                      child: Align(alignment: Alignment.topCenter, child: Container(height: 2, color: CricketColors.secondary.withValues(alpha: .12))),
                    ),
                  ),
                ),
                Opacity(
                  opacity: stageFade,
                  child: Transform.scale(scale: stageScale, child: _stageContent(size, ms)),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _stageContent(Size size, double ms) {
    final cx = size.width / 2, cy = size.height / 2;
    final d = (ms / 1150).clamp(0.0, 1.0); // the drop, trail and shadow last 1.15 s
    const easeIn = Cubic(.55, 0, 1, .45), easeOut = Cubic(0, .55, .45, 1);

    final dropY = keyframes(d, [
      Kf(0, -size.height * .62), Kf(.40, 0, easeIn), Kf(.44, -4, easeOut), Kf(.64, -140),
      Kf(.82, 0, easeIn), Kf(.91, -38, easeOut), Kf(1, 0, easeIn),
    ]);
    final sx = keyframes(d, const [Kf(0, 1), Kf(.40, 1.18, easeIn), Kf(.44, .94, easeOut), Kf(.64, 1), Kf(.82, 1.12, easeIn), Kf(.91, 1, easeOut), Kf(1, 1, easeIn)]);
    final sy = keyframes(d, const [Kf(0, 1), Kf(.40, .78, easeIn), Kf(.44, 1.08, easeOut), Kf(.64, 1), Kf(.82, .86, easeIn), Kf(.91, 1, easeOut), Kf(1, 1, easeIn)]);
    final shadowScale = keyframes(d, const [Kf(0, .15), Kf(.40, 1.1), Kf(.64, .55), Kf(.82, 1.05), Kf(.91, .85), Kf(1, 1)]);
    final shadowOpacity = keyframes(d, const [Kf(0, 0), Kf(.40, 1), Kf(.64, .5), Kf(.82, 1), Kf(1, 1)]);
    final trailOpacity = keyframes(d, const [Kf(0, 0), Kf(.25, .9), Kf(.40, 0), Kf(1, 0)]);
    final trailScale = keyframes(d, const [Kf(0, .1), Kf(.25, .8), Kf(.40, .2), Kf(1, 1)]);
    final wordSize = (size.width * .08).clamp(41.6, 86.4);

    return Stack(
      clipBehavior: Clip.none,
      children: [
        // red trail behind the falling ball
        Positioned(
          left: cx - 3, top: 0, width: 6, height: cy,
          child: Opacity(
            opacity: trailOpacity,
            child: Transform.scale(
              scaleY: trailScale,
              alignment: Alignment.bottomCenter,
              child: ImageFiltered(
                imageFilter: ImageFilter.blur(sigmaX: 2, sigmaY: 2),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(6),
                    gradient: LinearGradient(
                      begin: Alignment.topCenter, end: Alignment.bottomCenter, stops: const [0, .3, 1],
                      colors: [Colors.transparent, CricketColors.red.withValues(alpha: 0), CricketColors.red.withValues(alpha: .75)],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
        // shadow on the floor line
        Positioned(
          left: cx - 45, top: cy - 6, width: 90, height: 14,
          child: Opacity(
            opacity: shadowOpacity,
            child: Transform.scale(
              scale: shadowScale,
              child: ImageFiltered(
                imageFilter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
                child: DecoratedBox(decoration: BoxDecoration(color: Colors.black.withValues(alpha: .55), borderRadius: const BorderRadius.all(Radius.elliptical(45, 7)))),
              ),
            ),
          ),
        ),
        _shock(cx, cy, ms, 460, 700, CricketColors.secondary),
        _shock(cx, cy, ms, 940, 600, CricketColors.red),
        // the ball, squashing on each landing, seam spinning every 0.45 s
        Positioned(
          left: cx - 39, top: cy - 78, width: 78, height: 78,
          child: Transform.translate(
            offset: Offset(0, dropY),
            child: Transform(
              alignment: Alignment.bottomCenter,
              transform: Matrix4.diagonal3Values(sx, sy, 1),
              child: DecoratedBox(
                decoration: BoxDecoration(shape: BoxShape.circle, boxShadow: [BoxShadow(color: CricketColors.red.withValues(alpha: .55), blurRadius: 22, offset: const Offset(0, 12))]),
                child: CricketBall(size: 78, seamTurns: (ms % 450) / 450),
              ),
            ),
          ),
        ),
        // Full app name, centred and scaled to fit narrow phones.
        Positioned(
          left: 0, right: 0, top: cy + 34,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _word('SMART', CricketColors.light, ms, wordSize),
                  SizedBox(width: size.width < 560 ? 10 : 16),
                  _word('CRICKET', CricketColors.red, ms, wordSize),
                  SizedBox(width: size.width < 560 ? 10 : 16),
                  _word('AI', CricketColors.light, ms, wordSize),
                ],
              ),
            ),
          ),
        ),
        // The same supporting line as the web logo.
        Positioned(
          left: 0, right: 0, top: cy + (size.width < 560 ? 104 : 130),
          child: Builder(builder: (context) {
            final t = Curves.ease.transform(((ms - 1550) / 500).clamp(0, 1));
            return Text(
              'BATTING ANALYSIS & COACHING',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: CricketColors.secondary.withValues(alpha: .85 * t),
                fontSize: 13,
                fontWeight: FontWeight.w800,
                letterSpacing: 3 * (.9 - .45 * t),
              ),
            );
          }),
        ),
      ],
    );
  }

  Widget _shock(double cx, double cy, double ms, double start, double length, Color color) {
    final t = ((ms - start) / length).clamp(0.0, 1.0);
    if (ms < start) return const SizedBox.shrink();
    final e = Curves.easeOut.transform(t);
    return Positioned(
      left: cx - 30, top: cy - 8, width: 60, height: 16,
      child: Opacity(
        opacity: .95 * (1 - e),
        child: Transform(
          alignment: Alignment.center,
          transform: Matrix4.diagonal3Values(.4 + (7 - .4) * e, .4 + (4 - .4) * e, 1),
          child: DecoratedBox(decoration: BoxDecoration(border: Border.all(color: color, width: 3), borderRadius: const BorderRadius.all(Radius.elliptical(30, 8)))),
        ),
      ),
    );
  }

  Widget _word(String word, Color color, double ms, double fontSize) {
    const slam = Cubic(.2, 1.4, .4, 1);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < word.length; i++)
          Builder(builder: (context) {
            final raw = ((ms - (1050 + i * 45)) / 450).clamp(0.0, 1.0);
            final t = slam.transform(raw);
            final blur = 6 * (1 - raw);
            final letter = Text(word[i], style: CricketFonts.heading(fontSize, color: color).copyWith(letterSpacing: fontSize * .05));
            return Opacity(
              opacity: raw.clamp(0, 1),
              child: Transform.translate(
                offset: Offset(0, 40 * (1 - t)),
                child: Transform.rotate(
                  angle: -8 * (1 - t) * 3.14159 / 180,
                  child: Transform.scale(
                    scale: 1.6 - .6 * t,
                    child: blur > .2 ? ImageFiltered(imageFilter: ImageFilter.blur(sigmaX: blur, sigmaY: blur), child: letter) : letter,
                  ),
                ),
              ),
            );
          }),
      ],
    );
  }
}
