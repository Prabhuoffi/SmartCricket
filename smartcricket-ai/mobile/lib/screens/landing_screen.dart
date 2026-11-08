import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';

import '../ui/app_theme.dart';
import '../ui/brand.dart';
import '../ui/motion.dart';
import 'landing/hero_scene.dart';
import 'landing/intro_splash.dart';
import 'landing/sections.dart';

/// The app's landing page, following the website's landing page (frontend/index.html):
/// the same logo, colours, fonts, sections and motion, laid out like the website on a phone.
class LandingScreen extends StatefulWidget {
  const LandingScreen({
    super.key,
    required this.onLogin,
    this.showIntro = true,
  });

  final VoidCallback onLogin;

  /// The ball-drop intro plays when the app opens, not when returning from the login screen.
  final bool showIntro;

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen>
    with SingleTickerProviderStateMixin {
  final _scroll = ScrollController();
  final _demoKey = GlobalKey();
  late bool _intro = widget.showIntro;
  late final AnimationController _words = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  );

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() => setState(() {}));
    if (!_intro) _words.forward();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!motionOn(context)) _words.value = 1;
  }

  @override
  void dispose() {
    _scroll.dispose();
    _words.dispose();
    super.dispose();
  }

  void _introDone() {
    if (!mounted) return;
    setState(() => _intro = false);
    _words.forward();
  }

  /// Sign-up buttons burst into confetti first, like the website's register links.
  void _start(BuildContext context, Offset? at) {
    if (motionOn(context)) {
      final size = MediaQuery.sizeOf(context);
      _Confetti.burst(context, at ?? Offset(size.width / 2, size.height * .6));
      Future.delayed(const Duration(milliseconds: 420), widget.onLogin);
    } else {
      widget.onLogin();
    }
  }

  /// "See it in action": scroll so the live demo starts just below the floating nav bar.
  void _toDemo() {
    final box = _demoKey.currentContext?.findRenderObject();
    if (box == null || !_scroll.hasClients) return;
    final nav = MediaQuery.paddingOf(context).top + 64;
    final target =
        (RenderAbstractViewport.of(box).getOffsetToReveal(box, 0).offset -
                nav +
                40)
            .clamp(0.0, _scroll.position.maxScrollExtent);
    motionOn(context)
        ? _scroll.animateTo(
            target,
            duration: const Duration(milliseconds: 900),
            curve: kCricketEase,
          )
        : _scroll.jumpTo(target);
  }

  @override
  Widget build(BuildContext context) {
    final offset = _scroll.hasClients ? _scroll.offset : 0.0;
    final max = _scroll.hasClients && _scroll.position.hasContentDimensions
        ? _scroll.position.maxScrollExtent
        : 0.0;
    final progress = max > 0 ? (offset / max).clamp(0.0, 1.0) : 0.0;
    final top = MediaQuery.paddingOf(context).top;
    void start() => _start(context, null);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(
        statusBarColor: Colors.transparent,
      ),
      child: Scaffold(
        backgroundColor: CricketColors.cream,
        body: Stack(
          children: [
            CustomScrollView(
              key: const Key('landing-scroll'),
              controller: _scroll,
              slivers: [
                // one sliver, so the tilted ticker can overlap the bottom of the hero like on the website
                SliverToBoxAdapter(
                  child: Column(
                    children: [
                      _Hero(
                        words: _words,
                        scroll: offset,
                        onStart: _start,
                        onDemo: _toDemo,
                      ),
                      const ShotTicker(),
                    ],
                  ),
                ),
                const SliverToBoxAdapter(child: FeaturesSection()),
                const SliverToBoxAdapter(child: BoundaryRope()),
                SliverToBoxAdapter(child: WhatsNewSection(onStart: start)),
                const SliverToBoxAdapter(child: HowSection()),
                SliverToBoxAdapter(
                  child: KeyedSubtree(
                    key: _demoKey,
                    child: DemoSection(onStart: start),
                  ),
                ),
                const SliverToBoxAdapter(child: StatsBoard()),
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.only(bottom: 60),
                    child: BoundaryRope(reverse: true, phase: .5),
                  ),
                ),
                const SliverToBoxAdapter(child: AudienceSection()),
                const SliverToBoxAdapter(child: FaqSection()),
                SliverToBoxAdapter(
                  child: FinalCta(onStart: start, onLogin: widget.onLogin),
                ),
                SliverToBoxAdapter(
                  child: LandingFooter(onLogin: widget.onLogin, onStart: start),
                ),
              ],
            ),
            // nav: see-through over the hero, frosted dark green once scrolled
            Positioned(
              left: 0,
              right: 0,
              top: 0,
              child: _Nav(
                solid: offset > 40,
                topInset: top,
                onLogin: widget.onLogin,
                onStart: (at) => _start(context, at),
              ),
            ),
            // reading progress bar
            Positioned(
              left: 0,
              top: 0,
              height: 3,
              width: MediaQuery.sizeOf(context).width * progress,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [CricketColors.secondary, CricketColors.red],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: CricketColors.secondary.withValues(alpha: .7),
                      blurRadius: 12,
                    ),
                  ],
                ),
              ),
            ),
            if (_intro) Positioned.fill(child: IntroSplash(onDone: _introDone)),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- nav

class _Nav extends StatelessWidget {
  const _Nav({
    required this.solid,
    required this.topInset,
    required this.onLogin,
    required this.onStart,
  });
  final bool solid;
  final double topInset;
  final VoidCallback onLogin;
  final void Function(Offset? at) onStart;

  @override
  Widget build(BuildContext context) {
    final showSecondAction = MediaQuery.sizeOf(context).width >= 520;
    final bar = AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: EdgeInsets.fromLTRB(
        20,
        topInset + (solid ? 11 : 18),
        14,
        solid ? 11 : 18,
      ),
      decoration: BoxDecoration(
        color: solid
            ? CricketColors.night.withValues(alpha: .82)
            : Colors.transparent,
        border: Border(
          bottom: BorderSide(
            color: solid
                ? CricketColors.light.withValues(alpha: .08)
                : Colors.transparent,
          ),
        ),
      ),
      child: Row(
        children: [
          const Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: CricketBrand(light: true),
            ),
          ),
          _NavButton(
            key: const Key('landing-login'),
            label: 'Log in',
            onTap: onLogin,
          ),
          if (showSecondAction) ...[
            const SizedBox(width: 8),
            Builder(
              builder: (context) => _NavButton(
                label: 'Get started',
                red: true,
                onTap: () {
                  final box = context.findRenderObject() as RenderBox?;
                  onStart(box?.localToGlobal(box.size.center(Offset.zero)));
                },
              ),
            ),
          ],
        ],
      ),
    );
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: solid ? 16 : 0,
          sigmaY: solid ? 16 : 0,
        ),
        child: bar,
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    super.key,
    required this.label,
    required this.onTap,
    this.red = false,
  });
  final String label;
  final VoidCallback onTap;
  final bool red;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: label,
    excludeSemantics: true,
    child: Material(
      color: red ? CricketColors.red : Colors.transparent,
      shape: StadiumBorder(
        side: BorderSide(
          color: red
              ? Colors.transparent
              : CricketColors.light.withValues(alpha: .35),
          width: 2,
        ),
      ),
      child: InkWell(
        customBorder: const StadiumBorder(),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          child: Text(
            label,
            style: const TextStyle(
              color: CricketColors.light,
              fontSize: 13.5,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ),
    ),
  );
}

// ---------------------------------------------------------------- hero

class _Hero extends StatelessWidget {
  const _Hero({
    required this.words,
    required this.scroll,
    required this.onStart,
    required this.onDemo,
  });
  final Animation<double> words;
  final double scroll;
  final void Function(BuildContext context, Offset? at) onStart;
  final VoidCallback onDemo;

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final h1 = (size.width * .084).clamp(54.4, 115.2);
    // parallax: the text drifts down and fades as the page scrolls
    final fade = (1 - scroll / (size.height * .9)).clamp(0.0, 1.0);
    return Container(
      constraints: BoxConstraints(minHeight: size.height),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [CricketColors.night, CricketColors.night2],
        ),
      ),
      child: Stack(
        children: [
          const Positioned.fill(child: _HeroBackdrop()),
          Padding(
            padding: EdgeInsets.fromLTRB(
              20,
              MediaQuery.paddingOf(context).top + 104,
              20,
              70,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Transform.translate(
                  offset: Offset(0, scroll * .18),
                  child: Opacity(
                    opacity: fade,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const _LivePill(),
                        const SizedBox(height: 22),
                        _Headline(words: words, size: h1),
                        const SizedBox(height: 24),
                        const Reveal(
                          child: Text(
                            'Start with a batting photo for a posture report, or upload a clip to explore your movement. '
                            'Understand your measurements, follow a daily practice plan, and track your consistency. Trained video models also recognise shot types.',
                            style: TextStyle(
                              color: CricketColors.mutedLight,
                              fontSize: 16.5,
                              height: 1.65,
                            ),
                          ),
                        ),
                        const SizedBox(height: 36),
                        Reveal(
                          delay: 1,
                          child: Builder(
                            builder: (context) => Column(
                              children: [
                                PillButton(
                                  label: 'Start free analysis',
                                  arrow: true,
                                  onTap: () {
                                    final box =
                                        context.findRenderObject()
                                            as RenderBox?;
                                    onStart(
                                      context,
                                      box?.localToGlobal(
                                        box.size.center(Offset.zero),
                                      ),
                                    );
                                  },
                                ),
                                const SizedBox(height: 14),
                                PillButton(
                                  label: 'See it in action',
                                  kind: 'line',
                                  onTap: onDemo,
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 44),
                        const Reveal(delay: 2, child: _Trust()),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Transform.translate(
                  offset: Offset(0, scroll * -.08),
                  child: Reveal(
                    delay: 2,
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 520),
                        child: const HeroScene(),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// "LIVE AI ANALYSIS · FOR EVERY BATTER" with the pulsing red dot.
class _LivePill extends StatelessWidget {
  const _LivePill();

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.fromLTRB(10, 7, 14, 7),
    decoration: BoxDecoration(
      color: CricketColors.light.withValues(alpha: .08),
      borderRadius: BorderRadius.circular(99),
      border: Border.all(color: CricketColors.light.withValues(alpha: .14)),
    ),
    child: const Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        PulseDot(color: CricketColors.red, size: 9),
        SizedBox(width: 9),
        Flexible(
          child: Text(
            'LIVE AI ANALYSIS · FOR EVERY BATTER',
            style: TextStyle(
              color: CricketColors.light,
              fontSize: 11.5,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.75,
            ),
          ),
        ),
      ],
    ),
  );
}

/// "SEE EVERY STROKE. UNDERSTAND EVERY ANGLE." Each word rises out of a mask, 0.09 s apart.
class _Headline extends StatelessWidget {
  const _Headline({required this.words, required this.size});
  final Animation<double> words;
  final double size;

  static const _lines = [
    [('SEE', 0), ('EVERY', 0), ('STROKE.', 1)],
    [('UNDERSTAND', 2), ('EVERY', 0), ('ANGLE.', 0)],
  ];

  @override
  Widget build(BuildContext context) {
    final base = CricketFonts.heading(
      size,
      color: CricketColors.light,
      height: .92,
    ).copyWith(letterSpacing: size * .005);
    var index = 0;
    return Semantics(
      header: true,
      label: 'See every stroke. Understand every angle.',
      excludeSemantics: true,
      child: AnimatedBuilder(
        animation: words,
        builder: (context, _) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final line in _lines)
              Wrap(
                spacing: size * .22,
                children: [
                  for (final (word, kind) in line)
                    () {
                      final delay = 150 + (index++) * 90.0;
                      final t = kCricketEase.transform(
                        ((words.value * 1600 - delay) / 1000).clamp(0, 1),
                      );
                      final style = switch (kind) {
                        1 => base.copyWith(color: CricketColors.red),
                        2 => base.copyWith(
                          foreground: Paint()
                            ..style = PaintingStyle.stroke
                            ..strokeWidth = 2
                            ..color = CricketColors.secondary,
                        ),
                        _ => base,
                      };
                      final rising = Padding(
                        padding: EdgeInsets.only(bottom: size * .04),
                        child: Transform(
                          transform:
                              Matrix4.translationValues(
                                0,
                                size * 1.1 * (1 - t),
                                0,
                              )..multiply(
                                Matrix4.skewY(6 * (1 - t) * math.pi / 180),
                              ),
                          // STROKE.'s red glow (text-shadow 0 0 40px) is a blurred copy behind the word,
                          // because Android clips large text shadows to a hard rectangle
                          child: kind == 1
                              ? Stack(
                                  clipBehavior: Clip.none,
                                  children: [
                                    Positioned.fill(
                                      child: ImageFiltered(
                                        imageFilter: ImageFilter.blur(
                                          sigmaX: 16,
                                          sigmaY: 16,
                                          tileMode: TileMode.decal,
                                        ),
                                        child: Text(
                                          word,
                                          style: style.copyWith(
                                            color: CricketColors.red.withValues(
                                              alpha: .6,
                                            ),
                                          ),
                                        ),
                                      ),
                                    ),
                                    Text(word, style: style),
                                  ],
                                )
                              : Text(word, style: style),
                        ),
                      );
                      return t < 1 ? ClipRect(child: rising) : rising;
                    }(),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _Trust extends StatelessWidget {
  const _Trust();

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 14,
    runSpacing: 14,
    children: [
      for (final (n, label) in const [
        ('33', 'body points tracked'),
        ('15', 'batting shots'),
        ('8', 'joint angles measured'),
      ])
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          decoration: BoxDecoration(
            color: CricketColors.light.withValues(alpha: .05),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: CricketColors.light.withValues(alpha: .1),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                n,
                style: CricketFonts.heading(
                  32,
                  color: CricketColors.secondary,
                  height: 1.1,
                ).copyWith(letterSpacing: .64),
              ),
              Text(
                label,
                style: const TextStyle(
                  color: CricketColors.mutedLight,
                  fontSize: 12.8,
                ),
              ),
            ],
          ),
        ),
    ],
  );
}

/// The hero's stadium atmosphere: green and red glows, sweeping floodlights, a drifting grid,
/// a breathing light and crowd camera flashes.
class _HeroBackdrop extends StatelessWidget {
  const _HeroBackdrop();

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Loop(
      period: const Duration(seconds: 60),
      still: .1,
      builder: (context, t, _) =>
          CustomPaint(painter: _BackdropPainter(t * 60, motionOn(context))),
    ),
  );
}

class _BackdropPainter extends CustomPainter {
  _BackdropPainter(this.s, this.motion);
  final double s; // seconds
  final bool motion;

  static final _flashes = () {
    final r = math.Random(7);
    return List.generate(
      34,
      (_) => (
        r.nextDouble(),
        r.nextDouble(),
        r.nextDouble() * 4,
        3 + r.nextDouble() * 3,
      ),
    );
  }();

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    // radial glows: green at 78% 45%, red at 10% 100%
    canvas.drawRect(
      Offset.zero & size,
      Paint()
        ..shader =
            RadialGradient(
              colors: [
                CricketColors.pitch.withValues(alpha: .45),
                CricketColors.pitch.withValues(alpha: 0),
              ],
              stops: const [0, .65],
            ).createShader(
              Rect.fromCircle(center: Offset(w * .78, h * .45), radius: 600),
            ),
    );
    canvas.drawRect(
      Offset.zero & size,
      Paint()
        ..shader = RadialGradient(
          colors: [
            CricketColors.red.withValues(alpha: .22),
            CricketColors.red.withValues(alpha: 0),
          ],
          stops: const [0, .6],
        ).createShader(Rect.fromCircle(center: Offset(w * .1, h), radius: 500)),
    );

    // floodlight beams from the top corners, sweeping (9 s and 11 s)
    double sweep(double period, double from, double to) =>
        from +
        (to - from) * (1 - math.cos(2 * math.pi * (s % period) / period)) / 2;
    _beam(
      canvas,
      size,
      Offset(w * .15, -h * .2),
      motion ? sweep(9, -22, -6) : -14,
    );
    _beam(
      canvas,
      size,
      Offset(w * .85, -h * .2),
      motion ? sweep(11, 22, 6) : 14,
    );

    // grid drifting diagonally (64 px every 20 s), faded towards the edges
    final shift = motion ? (s % 20) / 20 * 64 : 0.0;
    final grid = Paint()
      ..color = CricketColors.light.withValues(alpha: .05 * .5)
      ..strokeWidth = 1;
    canvas.saveLayer(Offset.zero & size, Paint());
    for (var x = -64 + shift; x < w; x += 64) {
      canvas.drawLine(Offset(x, 0), Offset(x, h), grid);
    }
    for (var y = -64 + shift; y < h; y += 64) {
      canvas.drawLine(Offset(0, y), Offset(w, y), grid);
    }
    canvas.drawRect(
      Offset.zero & size,
      Paint()
        ..blendMode = BlendMode.dstIn
        ..shader =
            RadialGradient(
              colors: const [Colors.black, Colors.black, Colors.transparent],
              stops: const [0, .2, .75],
            ).createShader(
              Rect.fromCenter(
                center: Offset(w * .6, h * .5),
                width: w * 1.4,
                height: h,
              ),
            ),
    );
    canvas.restore();

    // breathing light, bottom right (7 s)
    final b = motion ? (1 - math.cos(2 * math.pi * (s % 7) / 7)) / 2 : 0.0;
    canvas.drawCircle(
      Offset(w + 160 - 280, h + 200 - 280),
      280 * (1 + .15 * b),
      Paint()
        ..shader =
            RadialGradient(
              colors: [
                CricketColors.secondary.withValues(alpha: .22 * (1 - .4 * b)),
                CricketColors.secondary.withValues(alpha: 0),
              ],
              stops: const [0, .65],
            ).createShader(
              Rect.fromCircle(
                center: Offset(w - 120, h - 80),
                radius: 280 * (1 + .15 * b),
              ),
            ),
    );

    // crowd camera flashes in the top 55%
    if (motion) {
      for (final (x, y, delay, dur) in _flashes) {
        final p = ((s - delay) % dur) / dur;
        if (p < .92 || p > .96) continue;
        final k = p < .94 ? (p - .92) / .02 : 1 - (p - .94) / .02 * .8;
        final c = Offset(x * w, y * h * .55);
        canvas.drawCircle(
          c,
          2 * (.4 + 1.2 * k),
          Paint()..color = Colors.white.withValues(alpha: k.clamp(0, 1)),
        );
        canvas.drawCircle(
          c,
          6,
          Paint()
            ..color = CricketColors.light.withValues(alpha: .9 * k.clamp(0, 1))
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
        );
      }
    }
  }

  void _beam(Canvas canvas, Size size, Offset apex, double degrees) {
    final length = size.height * 1.4;
    canvas.save();
    canvas.translate(apex.dx, apex.dy);
    canvas.rotate(degrees * math.pi / 180);
    final half = length * math.tan(9 * math.pi / 180);
    final path = Path()
      ..moveTo(0, 0)
      ..lineTo(-half, length)
      ..lineTo(half, length)
      ..close();
    canvas.drawPath(
      path,
      Paint()
        ..blendMode = BlendMode.screen
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6)
        ..shader = LinearGradient(
          colors: [
            Colors.transparent,
            CricketColors.light.withValues(alpha: .16 * .55),
            Colors.transparent,
          ],
        ).createShader(Rect.fromLTRB(-half, 0, half, length)),
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _BackdropPainter old) =>
      old.s != s || old.motion != motion;
}

// ---------------------------------------------------------------- confetti (sign-up buttons)

class _Confetti {
  static void burst(BuildContext context, Offset at) {
    final overlay = Overlay.maybeOf(context);
    if (overlay == null) return;
    late OverlayEntry entry;
    entry = OverlayEntry(
      builder: (_) => _ConfettiBurst(at: at, onDone: () => entry.remove()),
    );
    overlay.insert(entry);
  }
}

class _ConfettiBurst extends StatefulWidget {
  const _ConfettiBurst({required this.at, required this.onDone});
  final Offset at;
  final VoidCallback onDone;

  @override
  State<_ConfettiBurst> createState() => _ConfettiBurstState();
}

class _ConfettiBurstState extends State<_ConfettiBurst>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..forward().whenComplete(widget.onDone);
  static const _colors = [
    CricketColors.red,
    CricketColors.secondary,
    CricketColors.green,
    Colors.white,
  ];
  final _pieces = () {
    final r = math.Random();
    return List.generate(26, (i) {
      final a = r.nextDouble() * math.pi * 2, d = 60 + r.nextDouble() * 110;
      return (
        math.cos(a) * d,
        math.sin(a) * d - 40,
        r.nextDouble() * 720 - 360,
        _colors[i % 4],
      );
    });
  }();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => IgnorePointer(
    child: AnimatedBuilder(
      animation: _c,
      builder: (context, _) {
        final t = const Cubic(.2, .7, .3, 1).transform(_c.value);
        return Stack(
          children: [
            for (final (dx, dy, r, color) in _pieces)
              Positioned(
                left: widget.at.dx - 4 + dx * t,
                top: widget.at.dy - 7 + (dy + 120) * t,
                child: Opacity(
                  opacity: 1 - t,
                  child: Transform.rotate(
                    angle: r * t * math.pi / 180,
                    child: Container(
                      width: 9,
                      height: 14,
                      decoration: BoxDecoration(
                        color: color,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    ),
  );
}
