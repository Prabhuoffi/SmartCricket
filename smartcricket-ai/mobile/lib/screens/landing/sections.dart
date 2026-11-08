import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../ui/app_theme.dart';
import '../../ui/brand.dart';
import '../../ui/motion.dart';
import 'demo_pose.dart';

// ---------------------------------------------------------------- shared pieces

/// .eyebrow: a red dash then a small uppercase label.
class Eyebrow extends StatelessWidget {
  const Eyebrow(this.text, {super.key, this.light = false});
  final String text;
  final bool light;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 26,
        height: 3,
        decoration: BoxDecoration(
          color: CricketColors.red,
          borderRadius: BorderRadius.circular(3),
        ),
      ),
      const SizedBox(width: 10),
      Flexible(
        child: Text(
          text.toUpperCase(),
          style: CricketFonts.eyebrow.copyWith(
            color: light ? CricketColors.secondary : CricketColors.green,
          ),
        ),
      ),
    ],
  );
}

/// h2: big Anton uppercase heading; [accent] is the coloured end ("their own game.").
/// After it appears, a red bar sweeps in underneath, like .head h2::after.
class SectionTitle extends StatefulWidget {
  const SectionTitle(
    this.text,
    this.accent, {
    super.key,
    this.light = false,
    this.center = false,
    this.size = 38,
    this.underline = true,
  });
  final String text;
  final String accent;
  final bool light;
  final bool center;
  final double size;
  final bool underline;

  @override
  State<SectionTitle> createState() => _SectionTitleState();
}

class _SectionTitleState extends State<SectionTitle> {
  bool _in = false;

  @override
  Widget build(BuildContext context) {
    final base = CricketFonts.heading(
      widget.size,
      color: widget.light ? Colors.white : CricketColors.ink,
    );
    return Reveal(
      delay: 1,
      onReveal: () => Future.delayed(
        const Duration(milliseconds: 350),
        () => mounted ? setState(() => _in = true) : null,
      ),
      child: Column(
        crossAxisAlignment: widget.center
            ? CrossAxisAlignment.center
            : CrossAxisAlignment.start,
        children: [
          Text.rich(
            TextSpan(
              children: [
                TextSpan(text: '${widget.text.toUpperCase()} '),
                TextSpan(
                  text: widget.accent.toUpperCase(),
                  style: TextStyle(
                    color: widget.light
                        ? CricketColors.secondary
                        : CricketColors.red,
                  ),
                ),
              ],
            ),
            textAlign: widget.center ? TextAlign.center : TextAlign.start,
            style: base,
          ),
          if (widget.underline) ...[
            const SizedBox(height: 14),
            AnimatedContainer(
              duration: const Duration(milliseconds: 1100),
              curve: kCricketEase,
              width: _in ? 90 : 0,
              height: 6,
              decoration: BoxDecoration(
                color: CricketColors.red,
                borderRadius: BorderRadius.circular(6),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// .btn: pill buttons. [kind] is red, cream or line (outlined on dark).
class PillButton extends StatefulWidget {
  const PillButton({
    super.key,
    required this.label,
    required this.onTap,
    this.kind = 'red',
    this.arrow = false,
    this.expand = true,
  });
  final String label;
  final VoidCallback onTap;
  final String kind;
  final bool arrow;
  final bool expand;

  @override
  State<PillButton> createState() => _PillButtonState();
}

class _PillButtonState extends State<PillButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final red = widget.kind == 'red', cream = widget.kind == 'cream';
    final fg = red
        ? Colors.white
        : cream
        ? CricketColors.ink
        : CricketColors.light;
    final child = AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      curve: kCricketEase,
      transform: Matrix4.translationValues(0, _down ? -3 : 0, 0),
      padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 15),
      decoration: BoxDecoration(
        color: red
            ? CricketColors.red
            : cream
            ? CricketColors.secondary
            : Colors.transparent,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: red || cream
              ? Colors.transparent
              : (_down
                    ? CricketColors.secondary
                    : CricketColors.light.withValues(alpha: .35)),
          width: 2,
        ),
        boxShadow: red
            ? [
                BoxShadow(
                  color: CricketColors.red.withValues(alpha: _down ? .9 : .75),
                  blurRadius: _down ? 40 : 34,
                  offset: Offset(0, _down ? 20 : 14),
                  spreadRadius: -10,
                ),
              ]
            : cream
            ? [
                BoxShadow(
                  color: CricketColors.secondary.withValues(alpha: .6),
                  blurRadius: 34,
                  offset: const Offset(0, 14),
                  spreadRadius: -12,
                ),
              ]
            : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Flexible(
            child: Text(
              widget.label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: fg,
                fontSize: 15.5,
                fontWeight: FontWeight.w800,
                letterSpacing: .15,
              ),
            ),
          ),
          if (widget.arrow) ...[
            const SizedBox(width: 10),
            AnimatedSlide(
              offset: Offset(_down ? .28 : 0, 0),
              duration: const Duration(milliseconds: 250),
              curve: kCricketEase,
              child: Icon(Icons.arrow_forward_rounded, color: fg, size: 18),
            ),
          ],
        ],
      ),
    );
    return Semantics(
      button: true,
      label: widget.label,
      excludeSemantics: true,
      child: GestureDetector(
        onTapDown: (_) => setState(() => _down = true),
        onTapCancel: () => setState(() => _down = false),
        onTapUp: (_) => setState(() => _down = false),
        onTap: widget.onTap,
        child: widget.expand
            ? SizedBox(width: double.infinity, child: child)
            : child,
      ),
    );
  }
}

const _lead = TextStyle(
  fontSize: 16.5,
  height: 1.65,
  color: CricketColors.muted,
);
const _leadLight = TextStyle(
  fontSize: 16.5,
  height: 1.65,
  color: CricketColors.mutedLight,
);

// ---------------------------------------------------------------- marquee (broadcast ticker)

const shots = [
  'Cover Drive',
  'Defensive',
  'Down The Wicket',
  'Flick',
  'Hook',
  'Late Cut',
  'Lofted Legside',
  'Lofted Offside',
  'Pull',
  'Reverse Sweep',
  'Scoop',
  'Square Cut',
  'Straight Drive',
  'Sweep',
  'Upper Cut',
];

class ShotTicker extends StatelessWidget {
  const ShotTicker({super.key});

  static final _style = CricketFonts.heading(
    25.6,
    color: CricketColors.light,
    height: 1.25,
  ).copyWith(letterSpacing: 1);

  @override
  Widget build(BuildContext context) {
    // the width of one set of names, so the track can loop seamlessly at -50%
    var setWidth = 0.0;
    for (final s in shots) {
      final tp = TextPainter(
        text: TextSpan(text: s.toUpperCase(), style: _style),
        textDirection: TextDirection.ltr,
      )..layout();
      setWidth += tp.width + 40 + 14 + 40;
    }
    final items = [
      for (var i = 0; i < 2; i++)
        for (final s in shots) ...[
          Text(s.toUpperCase(), style: _style),
          const SizedBox(width: 40),
          Container(
            width: 14,
            height: 14,
            decoration: BoxDecoration(
              color: CricketColors.secondary,
              shape: BoxShape.circle,
              border: Border.all(color: CricketColors.ink, width: 3),
              boxShadow: const [
                BoxShadow(color: CricketColors.ink, spreadRadius: 0),
              ],
            ),
          ),
          const SizedBox(width: 40),
        ],
    ];
    final screen = MediaQuery.sizeOf(context).width;
    return Semantics(
      label: 'Shots the system recognises: ${shots.join(', ')}',
      excludeSemantics: true,
      child: SizedBox(
        height:
            46, // the band sits 26 px up into the hero, like the website's negative margin
        child: OverflowBox(
          maxWidth: screen * 1.04,
          maxHeight: 72,
          alignment: Alignment.bottomCenter,
          child: Transform.translate(
            offset: Offset.zero,
            child: Transform.rotate(
              angle: -2 * math.pi / 180,
              child: Container(
                width: screen * 1.04,
                height: 72,
                decoration: BoxDecoration(
                  color: CricketColors.red,
                  border: const Border.symmetric(
                    horizontal: BorderSide(color: CricketColors.ink, width: 4),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: CricketColors.red.withValues(alpha: .7),
                      blurRadius: 50,
                      offset: const Offset(0, 20),
                      spreadRadius: -20,
                    ),
                  ],
                ),
                child: ClipRect(
                  child: Loop(
                    period: const Duration(seconds: 34),
                    still: 0,
                    builder: (context, t, child) => Transform.translate(
                      offset: Offset(-setWidth * t, 0),
                      child: child,
                    ),
                    child: OverflowBox(
                      alignment: Alignment.centerLeft,
                      minWidth: 0,
                      maxWidth: setWidth * 2 + 10,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: items,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- features

class FeaturesSection extends StatelessWidget {
  const FeaturesSection({super.key});

  static const _items = [
    (
      Icons.photo_camera_outlined,
      'Photo posture report',
      '33 body points, 8 joint angles and a 3D view from one photo. Hidden joints are left out, never guessed.',
      'Know your stance',
    ),
    (
      Icons.videocam_outlined,
      'Video analysis',
      'Pose tracking on sampled frames, joint movement and a key moment. Longer videos can be split into detected strokes.',
      'Explore your movement',
    ),
    (
      Icons.co_present_outlined,
      'Live mirror',
      'Train in front of your camera: local pose tracking, live angles and an optional shot image saved with your session.',
      'New · on-device',
    ),
    (
      Icons.blur_on_rounded,
      'Shadow the pro',
      "A model player's ghost moves on your body. Copy it and get a live match score and stroke comparison.",
      'New · learn by copying',
    ),
    (
      Icons.fitness_center_rounded,
      'Daily training coach',
      'Three drills a day chosen from your own numbers, a check-in that respects soreness, levels and streaks.',
      'Practise the right thing',
    ),
    (
      Icons.chat_outlined,
      'AI coaching',
      'Ask about your results and training. When an AI provider is configured, feedback uses your stored measurements as context.',
      'Explain your results',
    ),
    (
      Icons.view_in_ar_outlined,
      'Estimated 3D angles',
      'Explore estimated joint positions in 3D alongside 2D measurements. Visibility and camera view still affect reliability.',
      'Another view of your posture',
    ),
    (
      Icons.verified_user_outlined,
      'Input quality check',
      'Every upload is scored for sharpness, light, framing and view, with a tip to film better next time.',
      'New · trust the numbers',
    ),
    (
      Icons.bar_chart_rounded,
      'Progress and reports',
      'Weekly coach summary, trend charts, history and one-click branded PDF reports.',
      'Track your growth',
    ),
  ];

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 54, 20, 80),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Reveal(child: Eyebrow('What you get')),
        const SizedBox(height: 14),
        const SectionTitle(
          'Everything a batter needs to read',
          'their own game.',
        ),
        const SizedBox(height: 16),
        const Reveal(
          delay: 1,
          child: Text(
            'Analysis, live training and a coach in one place. Built on a research dataset of 10,086 broadcast clips; every result comes with the evidence behind it.',
            style: _lead,
          ),
        ),
        const SizedBox(height: 36),
        for (var i = 0; i < _items.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 18),
            child: _FeatureCard(
              icon: _items[i].$1,
              title: _items[i].$2,
              text: _items[i].$3,
              tag: _items[i].$4,
              delay: i % 3,
            ),
          ),
      ],
    ),
  );
}

/// .feature: tap (instead of hover) turns the card dark green, tilts the icon and lifts the card.
class _FeatureCard extends StatefulWidget {
  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.text,
    required this.tag,
    required this.delay,
  });
  final IconData icon;
  final String title, text, tag;
  final int delay;

  @override
  State<_FeatureCard> createState() => _FeatureCardState();
}

class _FeatureCardState extends State<_FeatureCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _bounce = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 800),
  );
  bool _on = false;

  @override
  void dispose() {
    _bounce.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const d = Duration(milliseconds: 450);
    return Reveal(
      delay: widget.delay,
      onReveal: () {
        final motion = motionOn(context);
        Future.delayed(const Duration(milliseconds: 250), () {
          if (!mounted) return;
          motion ? _bounce.forward() : _bounce.value = 1;
        });
      },
      child: GestureDetector(
        onTap: () => setState(() => _on = !_on),
        child: AnimatedContainer(
          duration: d,
          curve: kCricketEase,
          transform: Matrix4.translationValues(0, _on ? -8 : 0, 0),
          padding: const EdgeInsets.all(28),
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            color: _on ? null : Colors.white,
            gradient: _on
                ? const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [CricketColors.night2, CricketColors.green],
                  )
                : null,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: CricketColors.line),
            boxShadow: _on
                ? [
                    BoxShadow(
                      color: CricketColors.pitch.withValues(alpha: .7),
                      blurRadius: 60,
                      offset: const Offset(0, 34),
                      spreadRadius: -30,
                    ),
                  ]
                : null,
          ),
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              Positioned(
                right: -88,
                top: -88,
                child: AnimatedOpacity(
                  duration: d,
                  opacity: _on ? 1 : 0,
                  child: Container(
                    width: 180,
                    height: 180,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: [
                          CricketColors.secondary.withValues(alpha: .55),
                          CricketColors.secondary.withValues(alpha: 0),
                        ],
                        stops: const [0, .7],
                      ),
                    ),
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AnimatedBuilder(
                    animation: _bounce,
                    builder: (context, child) {
                      final v = _bounce.value;
                      final scale = keyframes(v, const [
                        Kf(0, .4),
                        Kf(.6, 1.15, kCricketEase),
                        Kf(1, 1, kCricketEase),
                      ]);
                      final rot = keyframes(v, const [
                        Kf(0, -20),
                        Kf(.6, 6, kCricketEase),
                        Kf(1, 0, kCricketEase),
                      ]);
                      return Opacity(
                        opacity: (v / .6).clamp(0, 1),
                        child: Transform.rotate(
                          angle: rot * math.pi / 180,
                          child: Transform.scale(scale: scale, child: child),
                        ),
                      );
                    },
                    child: AnimatedRotation(
                      duration: d,
                      curve: kCricketEase,
                      turns: _on ? -10 / 360 : 0,
                      child: AnimatedScale(
                        duration: d,
                        scale: _on ? 1.08 : 1,
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 300),
                          width: 58,
                          height: 58,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(18),
                            color: _on ? CricketColors.secondary : null,
                            gradient: _on
                                ? null
                                : const LinearGradient(
                                    begin: Alignment.topLeft,
                                    end: Alignment.bottomRight,
                                    colors: [
                                      CricketColors.green,
                                      CricketColors.pitch,
                                    ],
                                  ),
                            boxShadow: [
                              BoxShadow(
                                color: CricketColors.pitch.withValues(
                                  alpha: .9,
                                ),
                                blurRadius: 28,
                                offset: const Offset(0, 14),
                                spreadRadius: -14,
                              ),
                            ],
                          ),
                          child: Icon(
                            widget.icon,
                            size: 27,
                            color: _on ? CricketColors.ink : Colors.white,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 22),
                  AnimatedDefaultTextStyle(
                    duration: d,
                    style: TextStyle(
                      fontFamily: CricketFonts.body,
                      fontSize: 19.5,
                      fontWeight: FontWeight.w700,
                      color: _on ? CricketColors.light : CricketColors.ink,
                    ),
                    child: Text(widget.title),
                  ),
                  const SizedBox(height: 8),
                  AnimatedDefaultTextStyle(
                    duration: d,
                    style: TextStyle(
                      fontFamily: CricketFonts.body,
                      fontSize: 15,
                      height: 1.6,
                      color: _on
                          ? CricketColors.mutedLight
                          : CricketColors.muted,
                    ),
                    child: Text(widget.text),
                  ),
                  const SizedBox(height: 18),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 11,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: _on
                          ? CricketColors.secondary
                          : CricketColors.red.withValues(alpha: .1),
                      borderRadius: BorderRadius.circular(99),
                    ),
                    child: Text(
                      widget.tag.toUpperCase(),
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w800,
                        letterSpacing: .7,
                        color: _on ? CricketColors.ink : CricketColors.red,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- boundary rope with a rolling ball

class BoundaryRope extends StatelessWidget {
  const BoundaryRope({super.key, this.reverse = false, this.phase = 0});
  final bool reverse;
  final double phase;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: SizedBox(
      height: 46,
      child: LayoutBuilder(
        builder: (context, box) {
          return Loop(
            period: const Duration(seconds: 7),
            still: .3,
            builder: (context, t, _) {
              final p = (t + phase) % 1;
              final x = reverse
                  ? box.maxWidth + 40 - (box.maxWidth + 80) * p
                  : -40 + (box.maxWidth + 80) * p;
              final spin = ((t * 7000) % 700) / 700;
              return Stack(
                children: [
                  Positioned(
                    left: 0,
                    right: 0,
                    top: 20,
                    height: 6,
                    child: CustomPaint(painter: _RopePainter()),
                  ),
                  Positioned(
                    left: x,
                    top: 23 - 26,
                    width: 30,
                    height: 30,
                    child: CricketBall(
                      size: 30,
                      seamTurns: reverse ? -spin : spin,
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    ),
  );
}

class _RopePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(
      Offset.zero & size,
      const Radius.circular(6),
    );
    canvas.drawRRect(
      r.shift(const Offset(0, 4)),
      Paint()
        ..color = CricketColors.ink.withValues(alpha: .25)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
    canvas.save();
    canvas.clipRRect(r);
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = CricketColors.secondary,
    );
    for (var x = 0.0; x < size.width; x += 40) {
      canvas.drawRect(
        Rect.fromLTWH(x, 0, 26, size.height),
        Paint()..color = CricketColors.red,
      );
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ---------------------------------------------------------------- what's new

class WhatsNewSection extends StatelessWidget {
  const WhatsNewSection({super.key, required this.onStart});
  final VoidCallback onStart;

  static const _items = [
    (
      Icons.bar_chart_rounded,
      'Guided sessions',
      'Your dashboard recommends the next step from your saved reports, check-in, drills, and daily question.',
      'A clear path through every session',
    ),
    (
      Icons.co_present_outlined,
      'Live mirror',
      'Skeleton and angles live, reps and holds counted automatically.',
      'Practise with feedback, not guesswork',
    ),
    (
      Icons.mic_none_rounded,
      'Voice coach',
      'Counts your reps and corrects you out loud; say "start" or "stop" hands-free.',
      'Eyes on the drill, not the screen',
    ),
    (
      Icons.blur_on_rounded,
      'Shadow the pro',
      'A gold ghost of a model player on your body, with a live match score.',
      'Learn a shot by copying it',
    ),
    (
      Icons.smartphone_rounded,
      'Phone camera and QR',
      'Scan a code and train with your phone propped up at the nets.',
      'Train anywhere you bat',
    ),
    (
      Icons.content_cut_rounded,
      'Whole nets videos',
      'Longer clips can be split into detected strokes, each with its own report.',
      'Review detected strokes individually',
    ),
    (
      Icons.view_in_ar_outlined,
      '3D pose and quality score',
      'Angles in 3D plus a quality check on every upload.',
      'Numbers you can trust',
    ),
  ];

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.fromLTRB(20, 70, 20, 70),
    decoration: const BoxDecoration(
      gradient: RadialGradient(
        center: Alignment(.7, -.2),
        radius: 1.1,
        colors: [Color(0xFF3C2420), CricketColors.night],
        stops: [0, .65],
      ),
    ),
    child: DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-.8, -.6),
          radius: 1.1,
          colors: [Color(0x591F9D55), Color(0x00062A1B)],
          stops: [0, .65],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Reveal(child: Eyebrow("What's new", light: true)),
          const SizedBox(height: 14),
          const SectionTitle(
            'Train live,',
            'with a coach that talks back.',
            light: true,
            underline: false,
          ),
          const SizedBox(height: 14),
          const Reveal(
            delay: 2,
            child: Text(
              'SmartCricket now goes beyond reports. Stand in front of your camera and the app coaches you in real time.',
              style: _leadLight,
            ),
          ),
          const SizedBox(height: 26),
          for (var i = 0; i < _items.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Reveal(
                delay: i % 3,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: CricketColors.secondary.withValues(alpha: .05),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: CricketColors.secondary.withValues(alpha: .1),
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(12),
                          gradient: const LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [CricketColors.pitch, CricketColors.green],
                          ),
                        ),
                        child: Icon(
                          _items[i].$1,
                          color: CricketColors.secondary,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _items[i].$2,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 15.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              _items[i].$3,
                              style: const TextStyle(
                                color: CricketColors.mutedLight,
                                fontSize: 13.5,
                                height: 1.45,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              _items[i].$4.toUpperCase(),
                              style: const TextStyle(
                                color: Color(0xFFFF7A8C),
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                letterSpacing: .55,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          const SizedBox(height: 16),
          Reveal(
            delay: 4,
            child: PillButton(
              label: 'Try live mirror',
              kind: 'cream',
              arrow: true,
              onTap: onStart,
            ),
          ),
          const SizedBox(height: 40),
          Reveal(
            delay: 2,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: const LiveMock(),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

/// .live-mock: a phone-style live mirror with the gold "pro" ghost, your swaying skeleton and the voice coach.
class LiveMock extends StatelessWidget {
  const LiveMock({super.key});

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: AspectRatio(
      aspectRatio: 4 / 5,
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(26),
          gradient: const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF0F3D27), CricketColors.night],
          ),
          border: Border.all(
            color: CricketColors.secondary.withValues(alpha: .14),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: .7),
              blurRadius: 80,
              offset: const Offset(0, 40),
              spreadRadius: -30,
            ),
          ],
        ),
        child: LayoutBuilder(
          builder: (context, box) {
            final w = box.maxWidth, h = box.maxHeight;
            return Stack(
              children: [
                Positioned(
                  left: w * .12,
                  top: h * .10,
                  width: w * .76,
                  height: h * .78,
                  child: Loop(
                    period: const Duration(milliseconds: 3200),
                    still: 0,
                    builder: (context, t, _) {
                      final s =
                          (1 - math.cos(2 * math.pi * t)) /
                          2; // ease-in-out, 0 → 1 → 0
                      return CustomPaint(painter: _MockBodyPainter(s));
                    },
                  ),
                ),
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  height: h * .28,
                  child: const DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [Colors.transparent, Color(0x59000000)],
                      ),
                    ),
                  ),
                ),
                Positioned(
                  top: 14,
                  left: 14,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: .4),
                      borderRadius: BorderRadius.circular(99),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Loop(
                          period: const Duration(milliseconds: 1200),
                          still: 0,
                          builder: (context, t, child) => Opacity(
                            opacity: t < .5 ? 1 - 1.4 * t : .3 + 1.4 * (t - .5),
                            child: child,
                          ),
                          child: Container(
                            width: 9,
                            height: 9,
                            decoration: const BoxDecoration(
                              color: Color(0xFFFF3B55),
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'LIVE ',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 11.5,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.15,
                          ),
                        ),
                        const Text(
                          '60 fps',
                          style: TextStyle(
                            color: CricketColors.mint,
                            fontSize: 11.5,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  left: 14,
                  top: 56,
                  child: Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: '8',
                          style: CricketFonts.heading(
                            41.6,
                            color: const Color(0xFFFF5A73),
                          ),
                        ),
                        TextSpan(
                          text: ' / 10 reps',
                          style: TextStyle(
                            color: CricketColors.secondary.withValues(
                              alpha: .8,
                            ),
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  right: 14,
                  top: 14,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '87%',
                        style: CricketFonts.heading(
                          35,
                          color: const Color(0xFFF5C542),
                        ),
                      ),
                      Text(
                        'MATCH WITH THE PRO',
                        style: TextStyle(
                          color: CricketColors.secondary.withValues(alpha: .75),
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          letterSpacing: .85,
                        ),
                      ),
                    ],
                  ),
                ),
                Positioned(
                  left: w * .5,
                  top: h * .66,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: CricketColors.pitch,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Text.rich(
                      TextSpan(
                        children: [
                          TextSpan(text: 'Front knee '),
                          TextSpan(
                            text: '148°',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ],
                      ),
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 12.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 14,
                  right: 14,
                  bottom: 16,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: CricketColors.red.withValues(alpha: .92),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Row(
                      children: [
                        Loop(
                          period: const Duration(milliseconds: 800),
                          still: 0,
                          builder: (context, t, _) {
                            final step = (t * 3).floor(); // steps(3)
                            return SizedBox(
                              width: 18,
                              height: 14,
                              child: Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  for (var b = 0; b < 4; b++)
                                    Container(
                                      width: 2,
                                      height: 14 - 8 * (((step + b) % 3) / 2),
                                      color: Colors.white,
                                    ),
                                ],
                              ),
                            );
                          },
                        ),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: Text(
                            '"Seven… bend a little more… eight!"',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 13.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    ),
  );
}

class _MockBodyPainter extends CustomPainter {
  _MockBodyPainter(this.sway);
  final double sway;

  static const _ghost = [
    [100, 40, 100, 120],
    [100, 60, 70, 95],
    [70, 95, 62, 128],
    [100, 60, 132, 88],
    [132, 88, 150, 70],
    [100, 120, 78, 175],
    [78, 175, 70, 235],
    [100, 120, 128, 172],
    [128, 172, 140, 232],
  ];
  static const _you = [
    [104, 44, 102, 122],
    [104, 64, 76, 98],
    [76, 98, 66, 130],
    [104, 64, 134, 92],
    [134, 92, 148, 78],
    [102, 122, 84, 176],
    [84, 176, 74, 236],
    [102, 122, 126, 176],
    [126, 176, 136, 234],
  ];

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 200, size.height / 260);
    final ghost = Paint()
      ..color = const Color(0xFFF5C542).withValues(alpha: .45)
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    for (final l in _ghost) {
      canvas.drawLine(
        Offset(l[0].toDouble(), l[1].toDouble()),
        Offset(l[2].toDouble(), l[3].toDouble()),
        ghost,
      );
    }
    canvas.drawCircle(const Offset(100, 28), 12, ghost);
    canvas.save();
    canvas.translate(100 - 5 * sway, 119.6);
    canvas.rotate(-2 * sway * math.pi / 180);
    canvas.translate(-100, -119.6);
    final you = Paint()
      ..color = CricketColors.pitch
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    for (final l in _you) {
      canvas.drawLine(
        Offset(l[0].toDouble(), l[1].toDouble()),
        Offset(l[2].toDouble(), l[3].toDouble()),
        you,
      );
    }
    canvas.drawCircle(const Offset(104, 32), 12, you);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _MockBodyPainter old) => old.sway != sway;
}

// ---------------------------------------------------------------- how it works

class HowSection extends StatefulWidget {
  const HowSection({super.key});

  @override
  State<HowSection> createState() => _HowSectionState();
}

class _HowSectionState extends State<HowSection> {
  int _lit = 0;
  static const _steps = [
    (
      'Capture',
      'Upload a side-on photo, a single stroke or a whole nets video, or go live with your laptop or phone camera.',
    ),
    (
      'Understand',
      'Review capture quality, visible joint measurements, and key video frames. Shot labels and heatmaps are available with trained models.',
    ),
    (
      'Practise and track',
      'Check in, follow your daily drills, and review your weekly summary. Your dashboard guides you to the next step.',
    ),
  ];

  void _play() {
    for (var i = 0; i < 3; i++) {
      Future.delayed(
        Duration(milliseconds: 500 + i * 650),
        () => mounted ? setState(() => _lit = i + 1) : null,
      );
    }
  }

  @override
  Widget build(BuildContext context) => Container(
    color: Colors.white,
    width: double.infinity,
    padding: const EdgeInsets.fromLTRB(20, 80, 20, 80),
    child: Column(
      children: [
        const Reveal(child: Eyebrow('Three steps')),
        const SizedBox(height: 14),
        const SectionTitle(
          'From your first capture to',
          'focused practice.',
          center: true,
        ),
        const SizedBox(height: 44),
        Reveal(
          onReveal: _play,
          child: Column(
            children: [
              for (var i = 0; i < 3; i++) ...[
                _Step(
                  number: i + 1,
                  title: _steps[i].$1,
                  text: _steps[i].$2,
                  lit: _lit > i,
                ),
                if (i < 2) const SizedBox(height: 44),
              ],
            ],
          ),
        ),
      ],
    ),
  );
}

class _Step extends StatelessWidget {
  const _Step({
    required this.number,
    required this.title,
    required this.text,
    required this.lit,
  });
  final int number;
  final String title, text;
  final bool lit;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: lit ? 1 : 0),
        duration: const Duration(milliseconds: 550),
        curve: Curves.linear,
        builder: (context, v, child) {
          // litPop: 40% scale 1.18 rotate -6°, then back
          final pop = lit
              ? keyframes(v, const [
                  Kf(0, 0),
                  Kf(.4, 1, kCricketEase),
                  Kf(1, 0, kCricketEase),
                ])
              : 0.0;
          return Transform.rotate(
            angle: -6 * pop * math.pi / 180,
            child: Transform.scale(scale: 1 + .18 * pop, child: child),
          );
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 400),
          width: 82,
          height: 82,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: lit ? CricketColors.red : CricketColors.night,
            borderRadius: BorderRadius.circular(26),
            boxShadow: [
              BoxShadow(
                color: CricketColors.night.withValues(alpha: .7),
                blurRadius: 34,
                offset: const Offset(0, 18),
                spreadRadius: -16,
              ),
            ],
          ),
          child: Text(
            '$number',
            style: CricketFonts.heading(
              35,
              color: lit ? Colors.white : CricketColors.secondary,
            ),
          ),
        ),
      ),
      const SizedBox(height: 24),
      Text(
        title,
        style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 8),
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 300),
        child: Text(
          text,
          textAlign: TextAlign.center,
          style: _lead.copyWith(fontSize: 15),
        ),
      ),
    ],
  );
}

// ---------------------------------------------------------------- live demo (real skeleton)

class DemoSection extends StatefulWidget {
  const DemoSection({super.key, required this.onStart});
  final VoidCallback onStart;

  @override
  State<DemoSection> createState() => _DemoSectionState();
}

class _DemoSectionState extends State<DemoSection>
    with TickerProviderStateMixin {
  late final AnimationController _draw = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2600),
  );
  late final AnimationController _curtain = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1150),
  );
  bool _numbers = false;

  static const _angles = [
    ('Front knee', 'left_knee'),
    ('Back knee', 'right_knee'),
    ('Front elbow', 'left_elbow'),
    ('Back elbow', 'right_elbow'),
  ];

  @override
  void dispose() {
    _draw.dispose();
    _curtain.dispose();
    super.dispose();
  }

  void _go() {
    if (!motionOn(context)) {
      _draw.value = 1;
      _curtain.value = 1;
      return;
    }
    _curtain.forward();
    _draw.forward();
  }

  @override
  Widget build(BuildContext context) {
    final aspect = demoPoseSize[0] / demoPoseSize[1];
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-.6, -.4),
          radius: 1.2,
          colors: [Color(0xFF104F33), CricketColors.night],
          stops: [0, .65],
        ),
      ),
      child: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 64, 20, 64),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Reveal(
                  onReveal: _go,
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 360),
                      child: Container(
                        clipBehavior: Clip.antiAlias,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(
                            color: CricketColors.light.withValues(alpha: .16),
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: .9),
                              blurRadius: 90,
                              offset: const Offset(0, 50),
                              spreadRadius: -40,
                            ),
                          ],
                        ),
                        child: AspectRatio(
                          aspectRatio: aspect,
                          child: AnimatedBuilder(
                            animation: _draw,
                            builder: (context, _) => Stack(
                              fit: StackFit.expand,
                              children: [
                                ColorFiltered(
                                  colorFilter: const ColorFilter.matrix([
                                    .55,
                                    0,
                                    0,
                                    0,
                                    0,
                                    0,
                                    .55,
                                    0,
                                    0,
                                    0,
                                    0,
                                    0,
                                    .55,
                                    0,
                                    0,
                                    0,
                                    0,
                                    0,
                                    1,
                                    0,
                                  ]),
                                  child: Image.asset(
                                    'assets/img/demo-batter.jpg',
                                    fit: BoxFit.cover,
                                    semanticLabel:
                                        'A batter moving onto the front foot',
                                  ),
                                ),
                                CustomPaint(
                                  painter: _SkeletonPainter(_draw.value * 2600),
                                ),
                                // scanline sweeping down once
                                LayoutBuilder(
                                  builder: (context, box) {
                                    final s = kCricketEase.transform(
                                      (_draw.value * 2600 / 1400).clamp(0, 1),
                                    );
                                    if (s >= 1) return const SizedBox.shrink();
                                    return Stack(
                                      children: [
                                        Positioned(
                                          left: 0,
                                          right: 0,
                                          height: box.maxHeight * .3,
                                          top: box.maxHeight * (-.3 + 1.3 * s),
                                          child: Opacity(
                                            opacity: 1 - s,
                                            child: Container(
                                              decoration: BoxDecoration(
                                                gradient: LinearGradient(
                                                  begin: Alignment.topCenter,
                                                  end: Alignment.bottomCenter,
                                                  colors: [
                                                    Colors.transparent,
                                                    CricketColors.secondary
                                                        .withValues(alpha: .2),
                                                  ],
                                                ),
                                                border: const Border(
                                                  bottom: BorderSide(
                                                    color:
                                                        CricketColors.secondary,
                                                    width: 2,
                                                  ),
                                                ),
                                                boxShadow: [
                                                  BoxShadow(
                                                    color: CricketColors
                                                        .secondary
                                                        .withValues(alpha: .6),
                                                    blurRadius: 20,
                                                    offset: const Offset(0, 6),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          ),
                                        ),
                                      ],
                                    );
                                  },
                                ),
                                const Positioned(
                                  left: 16,
                                  top: 16,
                                  child: _RealBadge(),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 36),
                const Reveal(child: Eyebrow('Live demo', light: true)),
                const SizedBox(height: 14),
                const SectionTitle(
                  'This is what',
                  'the AI sees.',
                  light: true,
                  size: 32,
                  underline: false,
                ),
                const SizedBox(height: 14),
                const Reveal(
                  delay: 2,
                  child: Text(
                    "This skeleton is the real result of SmartCricket's posture module on this photo: every body point detected, and each joint measured only when it is clearly visible.",
                    style: _leadLight,
                  ),
                ),
                const SizedBox(height: 22),
                Reveal(
                  delay: 3,
                  onReveal: () => setState(() => _numbers = true),
                  child: GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    childAspectRatio: 1.55,
                    children: [
                      for (final (label, key) in _angles)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 12,
                          ),
                          decoration: BoxDecoration(
                            color: CricketColors.light.withValues(alpha: .06),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: CricketColors.light.withValues(alpha: .12),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                label.toUpperCase(),
                                style: TextStyle(
                                  color: CricketColors.light.withValues(
                                    alpha: .7,
                                  ),
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 1,
                                ),
                              ),
                              CountUp(
                                to: demoPoseAngles[key]!,
                                play: _numbers,
                                decimals: 1,
                                suffix: '°',
                                style: CricketFonts.heading(
                                  28.8,
                                  color: CricketColors.secondary,
                                  height: 1.15,
                                ),
                              ),
                              const SizedBox(height: 8),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(6),
                                child: Container(
                                  height: 6,
                                  color: CricketColors.light.withValues(
                                    alpha: .1,
                                  ),
                                  alignment: Alignment.centerLeft,
                                  child: AnimatedFractionallySizedBox(
                                    duration: const Duration(
                                      milliseconds: 1500,
                                    ),
                                    curve: kCricketEase,
                                    widthFactor: _numbers
                                        ? demoPoseAngles[key]! / 180
                                        : 0,
                                    child: const DecoratedBox(
                                      decoration: BoxDecoration(
                                        gradient: LinearGradient(
                                          colors: [
                                            CricketColors.green,
                                            CricketColors.secondary,
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 22),
                Reveal(
                  delay: 4,
                  child: PillButton(
                    label: 'Try it with your own photo',
                    kind: 'cream',
                    arrow: true,
                    onTap: widget.onStart,
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  'Photo: Acabashi, Wikimedia Commons, CC BY-SA 4.0. Overlay produced by SmartCricket AI.',
                  style: TextStyle(
                    color: CricketColors.light.withValues(alpha: .55),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          // curtain wipe: green and red panels slide away diagonally
          Positioned.fill(
            child: IgnorePointer(
              child: AnimatedBuilder(
                animation: _curtain,
                builder: (context, _) {
                  final c = const Cubic(.77, 0, .18, 1);
                  final a = c.transform(_curtain.value);
                  final b = c.transform(
                    ((_curtain.value * 1150 - 80) / 1070).clamp(0, 1),
                  );
                  if (_curtain.value >= 1) return const SizedBox.shrink();
                  return ClipRect(
                    child: LayoutBuilder(
                      builder: (context, box) {
                        final w = box.maxWidth * .7;
                        Widget panel(Color color, double left, double shift) =>
                            Positioned(
                              left: left + shift * w * 1.4,
                              top: -box.maxHeight * .1,
                              width: w,
                              height: box.maxHeight * 1.2,
                              child: Transform(
                                transform: Matrix4.skewX(-14 * math.pi / 180),
                                alignment: Alignment.center,
                                child: ColoredBox(color: color),
                              ),
                            );
                        return Stack(
                          children: [
                            panel(CricketColors.green, -box.maxWidth * .12, -a),
                            panel(
                              CricketColors.red,
                              box.maxWidth * 1.12 - w,
                              b,
                            ),
                          ],
                        );
                      },
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RealBadge extends StatelessWidget {
  const _RealBadge();

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
    decoration: BoxDecoration(
      color: CricketColors.night.withValues(alpha: .75),
      borderRadius: BorderRadius.circular(99),
      border: Border.all(color: CricketColors.light.withValues(alpha: .2)),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const PulseDot(color: CricketColors.secondary, size: 8),
        const SizedBox(width: 8),
        const Text(
          'REAL OUTPUT',
          style: TextStyle(
            color: Colors.white,
            fontSize: 11.5,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.4,
          ),
        ),
      ],
    ),
  );
}

/// The .live dot: a ring grows out of it and fades every 1.6 s.
class PulseDot extends StatelessWidget {
  const PulseDot({super.key, required this.color, this.size = 9});
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) => Loop(
    period: const Duration(milliseconds: 1600),
    still: 0,
    builder: (context, t, _) {
      final ring = t < .7 ? t / .7 : 1.0;
      return Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: .8 * (1 - ring)),
              spreadRadius: 10 * ring,
            ),
          ],
        ),
      );
    },
  );
}

class _SkeletonPainter extends CustomPainter {
  _SkeletonPainter(this.ms);
  final double ms;

  @override
  void paint(Canvas canvas, Size size) {
    final lm = demoPoseLandmarks;
    Offset p(int i) => Offset(lm[i][0] * size.width, lm[i][1] * size.height);
    final k = size.width / 100; // the website draws in a 100-wide view box
    // bones draw in one after another (0.5 s + 0.07 s each, 0.6 s long)
    final bone = Paint()
      ..color = CricketColors.secondary
      ..strokeWidth = .85 * k
      ..strokeCap = StrokeCap.round;
    final glow = Paint()
      ..color = CricketColors.secondary.withValues(alpha: .9)
      ..strokeWidth = .85 * k
      ..strokeCap = StrokeCap.round
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, 1.2 * k);
    for (var i = 0; i < demoPoseEdges.length; i++) {
      final a = demoPoseEdges[i][0], b = demoPoseEdges[i][1];
      if (math.min(lm[a][2], lm[b][2]) < .5) continue;
      final t = kCricketEase.transform(((ms - 500 - i * 70) / 600).clamp(0, 1));
      if (t <= 0) continue;
      final end = Offset.lerp(p(a), p(b), t)!;
      canvas.drawLine(p(a), end, glow);
      canvas.drawLine(p(a), end, bone);
    }
    // joints pop in (overshoot to 1.35)
    for (var i = 0; i < lm.length; i++) {
      if ((i > 0 && i < 11) || lm[i][2] < .5) continue;
      final t = ((ms - 400 - i * 30) / 450).clamp(0.0, 1.0);
      if (t <= 0) continue;
      final s = keyframes(t, const [
        Kf(0, 0),
        Kf(.7, 1.35, kCricketEase),
        Kf(1, 1, kCricketEase),
      ]);
      canvas.drawCircle(p(i), 1.1 * k * s, Paint()..color = CricketColors.red);
      canvas.drawCircle(
        p(i),
        1.1 * k * s,
        Paint()
          ..color = Colors.white
          ..style = PaintingStyle.stroke
          ..strokeWidth = .4 * k,
      );
    }
    // angle labels fade in
    const labels = [
      ('left_knee', 25),
      ('right_knee', 26),
      ('left_elbow', 13),
      ('right_elbow', 14),
    ];
    for (var j = 0; j < labels.length; j++) {
      final t = ((ms - 1800 - j * 150) / 500).clamp(0.0, 1.0);
      if (t <= 0) continue;
      final pos = p(labels[j].$2) + Offset(2.5 * k, -2 * k - 3 * k);
      final text = '${demoPoseAngles[labels[j].$1]!.round()}°';
      final outline = TextPainter(
        text: TextSpan(
          text: text,
          style: TextStyle(
            fontSize: 3 * k,
            fontWeight: FontWeight.w800,
            foreground: Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = k
              ..color = CricketColors.green.withValues(alpha: t),
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final fill = TextPainter(
        text: TextSpan(
          text: text,
          style: TextStyle(
            fontSize: 3 * k,
            fontWeight: FontWeight.w800,
            color: Colors.white.withValues(alpha: t),
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      outline.paint(canvas, pos);
      fill.paint(canvas, pos);
    }
  }

  @override
  bool shouldRepaint(covariant _SkeletonPainter old) => old.ms != ms;
}

// ---------------------------------------------------------------- scoreboard stats

class StatsBoard extends StatefulWidget {
  const StatsBoard({super.key});

  @override
  State<StatsBoard> createState() => _StatsBoardState();
}

class _StatsBoardState extends State<StatsBoard> {
  bool _play = false;
  static const _stats = [
    (10086.0, 'clips in the research dataset', CricketColors.secondary),
    (15.0, 'shot classes for trained models', CricketColors.red),
    (33.0, 'body points tracked', CricketColors.mint),
    (8.0, 'joint angles with visibility checks', CricketColors.secondary),
  ];

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 80, 20, 80),
    child: Reveal(
      onReveal: () => setState(() => _play = true),
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          color: CricketColors.night,
          borderRadius: BorderRadius.circular(28),
          border: Border.all(color: CricketColors.light.withValues(alpha: .06)),
          boxShadow: [
            BoxShadow(
              color: CricketColors.night.withValues(alpha: .8),
              blurRadius: 70,
              offset: const Offset(0, 40),
              spreadRadius: -40,
            ),
          ],
        ),
        child: Stack(
          children: [
            // scoreboard bulbs blinking along the top
            Positioned(
              left: 18,
              right: 18,
              top: 10,
              child: Loop(
                period: const Duration(seconds: 1),
                still: 0,
                builder: (context, t, _) => Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    for (var i = 0; i < 28; i++)
                      Builder(
                        builder: (context) {
                          final on = ((t - (i % 4) * .25) % 1) < .5;
                          return Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: CricketColors.secondary.withValues(
                                alpha: on ? 1 : .2,
                              ),
                              boxShadow: on
                                  ? [
                                      BoxShadow(
                                        color: CricketColors.secondary
                                            .withValues(alpha: .9),
                                        blurRadius: 8,
                                      ),
                                    ]
                                  : null,
                            ),
                          );
                        },
                      ),
                  ],
                ),
              ),
            ),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              childAspectRatio: 1.05,
              children: [
                for (final (n, label, color) in _stats)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(14, 30, 14, 20),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        FittedBox(
                          child: CountUp(
                            to: n,
                            play: _play,
                            style: CricketFonts.heading(44.8, color: color)
                                .copyWith(
                                  shadows: [
                                    Shadow(
                                      color: color.withValues(alpha: .4),
                                      blurRadius: 30,
                                    ),
                                  ],
                                ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          label.toUpperCase(),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: CricketColors.mutedLight,
                            fontWeight: FontWeight.w700,
                            fontSize: 11.5,
                            letterSpacing: 1.4,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

// ---------------------------------------------------------------- audience

class AudienceSection extends StatelessWidget {
  const AudienceSection({super.key});

  static const _cards = [
    (
      '01',
      'Players',
      'Understand your own stroke without waiting for a coach.',
      [
        'Posture report from one photo',
        'Live mirror with a voice coach',
        'Daily drills, streaks and levels',
      ],
      [CricketColors.green, CricketColors.night2],
    ),
    (
      '02',
      'Coaches',
      'Back up what you see with numbers you can show.',
      [
        'Reference movement comparisons',
        'Estimated 2D and 3D joint angles',
        'One-click PDF reports to share',
      ],
      [CricketColors.red, Color(0xFF8F0B20)],
    ),
    (
      '03',
      'Academies',
      'Give every player structured feedback, at scale.',
      [
        'Admin console for every player',
        'See who needs a nudge',
        'Reference clips for each shot',
      ],
      [CricketColors.night2, CricketColors.night],
    ),
  ];

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 0, 20, 80),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Reveal(child: Eyebrow('Made for')),
        const SizedBox(height: 14),
        const SectionTitle('Players, coaches', 'and academies.'),
        const SizedBox(height: 40),
        for (var i = 0; i < _cards.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 18),
            child: Reveal(
              delay: i,
              child: Container(
                width: double.infinity,
                clipBehavior: Clip.antiAlias,
                padding: const EdgeInsets.fromLTRB(28, 32, 28, 32),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(24),
                  gradient: LinearGradient(
                    begin: const Alignment(-.6, -1),
                    end: const Alignment(.6, 1),
                    colors: _cards[i].$5,
                  ),
                ),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Positioned(
                      right: -6,
                      bottom: -72,
                      child: Text(
                        _cards[i].$1,
                        style: CricketFonts.heading(
                          144,
                          color: Colors.white.withValues(alpha: .12),
                        ),
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _cards[i].$2.toUpperCase(),
                          style: CricketFonts.heading(
                            32,
                            color: Colors.white,
                          ).copyWith(letterSpacing: .64),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _cards[i].$3,
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: .88),
                            fontSize: 15,
                            height: 1.6,
                          ),
                        ),
                        const SizedBox(height: 20),
                        for (final li in _cards[i].$4)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(
                                    color: CricketColors.secondary,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    li,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 15,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    ),
  );
}

// ---------------------------------------------------------------- FAQ

class FaqSection extends StatefulWidget {
  const FaqSection({super.key});

  @override
  State<FaqSection> createState() => _FaqSectionState();
}

class _FaqSectionState extends State<FaqSection> {
  int? _open;
  static const _qa = [
    (
      'Do I need special equipment?',
      'No. A phone camera is enough. Film side-on, at hip height, with the whole batter in view.',
    ),
    (
      'Does a photo tell me which shot I played?',
      'A photo gives a posture report. Upload a short clip for movement analysis; shot recognition also requires trained video models to be installed.',
    ),
    (
      'Who can see my photos and videos?',
      'Only you. Files stay on the SmartCricket server and are linked to your account. The AI coach receives your numbers only, never your images.',
    ),
    (
      'How accurate is it?',
      'Accuracy depends on the installed model, capture quality, camera view, and how closely the footage matches the training data. The admin Model results page shows imported evaluation metrics. Prediction confidence is an estimate, not a guarantee.',
    ),
    (
      'Does live mirror record or upload my camera?',
      'Live pose tracking runs on your device. Saving a session stores its numerical summary and one automatically chosen shot image when available. You can view or delete that image in Live history. If you choose web shot recognition, sampled frames are uploaded for analysis and then discarded.',
    ),
    (
      'Can I use my phone at the nets?',
      'Yes. Prop your phone up side-on, sign in and start your live session. You can also upload a whole nets video on the website: each shot is found and analysed separately.',
    ),
    (
      'Does the AI coach replace a real coach?',
      'No. It explains your measured results in plain words and suggests drills. Angles are 2D estimates from one camera, not a judgement of right or wrong technique.',
    ),
  ];

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 0, 20, 80),
    child: Column(
      children: [
        const Reveal(child: Eyebrow('Questions')),
        const SizedBox(height: 14),
        const SectionTitle('Good to', 'know.', center: true),
        const SizedBox(height: 40),
        for (var i = 0; i < _qa.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Reveal(
              delay: math.min(i, 3),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                padding: const EdgeInsets.symmetric(horizontal: 22),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: _open == i
                        ? CricketColors.pitch.withValues(alpha: .4)
                        : CricketColors.line,
                  ),
                  boxShadow: _open == i
                      ? [
                          BoxShadow(
                            color: CricketColors.pitch.withValues(alpha: .6),
                            blurRadius: 40,
                            offset: const Offset(0, 20),
                            spreadRadius: -26,
                          ),
                        ]
                      : null,
                ),
                child: Column(
                  children: [
                    Semantics(
                      button: true,
                      expanded: _open == i,
                      child: InkWell(
                        onTap: () =>
                            setState(() => _open = _open == i ? null : i),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 20),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  _qa[i].$1,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 16.5,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 16),
                              AnimatedRotation(
                                duration: const Duration(milliseconds: 400),
                                curve: kCricketEase,
                                turns: _open == i ? 135 / 360 : 0,
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 300),
                                  width: 34,
                                  height: 34,
                                  alignment: Alignment.center,
                                  decoration: BoxDecoration(
                                    color: _open == i
                                        ? CricketColors.red
                                        : CricketColors.cream,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    '+',
                                    style: TextStyle(
                                      fontSize: 21,
                                      fontWeight: FontWeight.w700,
                                      color: _open == i
                                          ? Colors.white
                                          : CricketColors.green,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    AnimatedSize(
                      duration: const Duration(milliseconds: 450),
                      curve: kCricketEase,
                      alignment: Alignment.topCenter,
                      child: _open == i
                          ? Padding(
                              padding: const EdgeInsets.only(bottom: 22),
                              child: Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  _qa[i].$2,
                                  style: _lead.copyWith(fontSize: 15),
                                ),
                              ),
                            )
                          : const SizedBox(width: double.infinity),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    ),
  );
}

// ---------------------------------------------------------------- final call to action and footer

class FinalCta extends StatelessWidget {
  const FinalCta({super.key, required this.onStart, required this.onLogin});
  final VoidCallback onStart;
  final VoidCallback onLogin;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 20),
    child: Reveal(
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(34),
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              CricketColors.night2,
              CricketColors.green,
              Color(0xFF137A49),
            ],
            stops: [0, .6, 1],
          ),
        ),
        child: Stack(
          children: [
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: const Alignment(.84, -1),
                    radius: 1.2,
                    colors: [
                      CricketColors.pitch.withValues(alpha: .55),
                      CricketColors.pitch.withValues(alpha: 0),
                    ],
                    stops: const [0, .65],
                  ),
                ),
              ),
            ),
            // the dashed seam ring slowly turning in the corner
            Positioned(
              right: -70,
              bottom: -90,
              child: Loop(
                period: const Duration(seconds: 30),
                still: 0,
                builder: (context, t, child) =>
                    Transform.rotate(angle: t * 2 * math.pi, child: child),
                child: CustomPaint(
                  size: const Size(320, 320),
                  painter: _DashedRingPainter(),
                ),
              ),
            ),
            Positioned(
              left: 0,
              top: 0,
              bottom: 0,
              width: 8,
              child: Container(color: CricketColors.red),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(36, 44, 28, 44),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(text: 'READY TO SEE YOUR BATTING '),
                        TextSpan(
                          text: 'THE WAY THE AI DOES?',
                          style: TextStyle(
                            color: CricketColors.secondary.withValues(alpha: 1),
                          ),
                        ),
                      ],
                    ),
                    style: CricketFonts.heading(36, color: Colors.white),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Create a free account and analyse your first photo in under a minute.',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: .9),
                      fontSize: 16,
                      height: 1.6,
                    ),
                  ),
                  const SizedBox(height: 28),
                  PillButton(
                    label: 'Create free account',
                    kind: 'cream',
                    onTap: onStart,
                  ),
                  const SizedBox(height: 12),
                  PillButton(
                    label: 'I already have an account',
                    kind: 'line',
                    onTap: onLogin,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _DashedRingPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = CricketColors.red.withValues(alpha: .7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    final r = size.width / 2 - 1.5;
    const dashes = 64;
    for (var i = 0; i < dashes; i++) {
      final a = i * 2 * math.pi / dashes;
      canvas.drawArc(
        Rect.fromCircle(center: size.center(Offset.zero), radius: r),
        a,
        math.pi / dashes,
        false,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class LandingFooter extends StatelessWidget {
  const LandingFooter({
    super.key,
    required this.onLogin,
    required this.onStart,
  });
  final VoidCallback onLogin;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    const muted = TextStyle(
      color: CricketColors.mutedLight,
      fontSize: 14.5,
      height: 1.65,
    );
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 90),
      padding: EdgeInsets.fromLTRB(
        20,
        56,
        20,
        30 + MediaQuery.paddingOf(context).bottom,
      ),
      color: CricketColors.night,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CricketBrand(light: true),
          const SizedBox(height: 14),
          const Text(
            'An explainable multimodal cricket shot analysis and intelligent virtual coaching system. M.E. Computer Science and Engineering final-year project.',
            style: muted,
          ),
          const SizedBox(height: 28),
          const Text(
            'Account',
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 8),
          InkWell(
            onTap: onLogin,
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text('Log in', style: muted),
            ),
          ),
          InkWell(
            onTap: onStart,
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text('Create account', style: muted),
            ),
          ),
          const SizedBox(height: 30),
          Container(
            height: 1,
            color: CricketColors.light.withValues(alpha: .1),
          ),
          const SizedBox(height: 20),
          Opacity(
            opacity: .75,
            child: Text(
              'Shot recognition is trained on CricShot10k (Dihan et al., IEEE Access, 2026), used for non-commercial research. '
              'Demo photo: Acabashi, Wikimedia Commons, CC BY-SA 4.0. Joint angles are 2D estimates from one camera view and are not medical advice.\n'
              '© 2026 SmartCricket AI · Academic project',
              style: muted.copyWith(fontSize: 12.5, height: 1.6),
            ),
          ),
        ],
      ),
    );
  }
}
