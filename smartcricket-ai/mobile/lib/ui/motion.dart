import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'app_theme.dart';

/// False when the phone asks for reduced motion, the same as the website's prefers-reduced-motion.
bool motionOn(BuildContext context) => !(MediaQuery.maybeDisableAnimationsOf(context) ?? false);

/// One keyframe of a CSS-style animation: the value at [at] (0 to 1), eased from the previous keyframe by [curve].
class Kf<T> {
  const Kf(this.at, this.value, [this.curve = Curves.linear]);
  final double at;
  final T value;
  final Curve curve;
}

/// Reads a CSS @keyframes list at time [t] (0 to 1). Like CSS, each segment uses its own easing.
double keyframes(double t, List<Kf<double>> keys) {
  if (t <= keys.first.at) return keys.first.value;
  for (var i = 1; i < keys.length; i++) {
    final a = keys[i - 1], b = keys[i];
    if (t <= b.at) {
      final span = b.at - a.at;
      final local = span <= 0 ? 1.0 : (t - a.at) / span;
      return a.value + (b.value - a.value) * b.curve.transform(local.clamp(0, 1));
    }
  }
  return keys.last.value;
}

/// The website's scroll reveal (.rv): fades in and rises 40 px the first time 18% of it is on screen.
class Reveal extends StatefulWidget {
  const Reveal({super.key, required this.child, this.delay = 0, this.onReveal, this.offset = 40});

  final Widget child;

  /// Steps of 0.1 s, like the website's .d1 to .d5 classes.
  final int delay;
  final VoidCallback? onReveal;
  final double offset;

  @override
  State<Reveal> createState() => _RevealState();
}

class _RevealState extends State<Reveal> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1000));
  ScrollPosition? _position;
  bool _shown = false;
  bool _queued = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _position?.removeListener(_onScroll);
    _position = Scrollable.maybeOf(context)?.position;
    _position?.addListener(_onScroll);
    _onScroll();
  }

  // Scroll listeners run before the new layout, so measure after the frame has been laid out.
  void _onScroll() {
    if (_shown || _queued) return;
    _queued = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _queued = false;
      _check();
    });
    WidgetsBinding.instance.ensureVisualUpdate();
  }

  void _check() {
    if (_shown || !mounted) return;
    final box = context.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return;
    final top = box.localToGlobal(Offset.zero).dy;
    final screen = MediaQuery.sizeOf(context).height;
    final visible = math.min(top + box.size.height, screen) - math.max(top, 0);
    if (visible >= math.min(box.size.height, screen) * .18) {
      _shown = true;
      _position?.removeListener(_onScroll);
      if (!motionOn(context)) {
        _c.value = 1;
        widget.onReveal?.call();
        return;
      }
      Future.delayed(Duration(milliseconds: widget.delay * 100), () {
        if (!mounted) return;
        _c.forward();
        widget.onReveal?.call();
      });
    }
  }

  @override
  void dispose() {
    _position?.removeListener(_onScroll);
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _c,
    child: widget.child,
    builder: (context, child) {
      final t = kCricketEase.transform(_c.value);
      return Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, widget.offset * (1 - t)), child: child),
      );
    },
  );
}

/// Counts up to [to] like the website's countTo(): 1.6 s with an ease-out-quart curve.
class CountUp extends StatefulWidget {
  const CountUp({super.key, required this.to, required this.play, this.decimals = 0, this.suffix = '', this.style});

  final double to;
  final bool play;
  final int decimals;
  final String suffix;
  final TextStyle? style;

  @override
  State<CountUp> createState() => _CountUpState();
}

class _CountUpState extends State<CountUp> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600));

  @override
  void didUpdateWidget(CountUp old) {
    super.didUpdateWidget(old);
    if (widget.play && !old.play) {
      motionOn(context) ? _c.forward() : _c.value = 1;
    }
  }

  @override
  void initState() {
    super.initState();
    if (widget.play) _c.forward();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  static String _group(String digits) => digits.replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _c,
    builder: (context, _) {
      final e = 1 - math.pow(1 - _c.value, 4);
      final n = widget.to * e;
      final text = widget.decimals == 0 ? _group(n.round().toString()) : n.toStringAsFixed(widget.decimals);
      return Text('$text${widget.suffix}', style: widget.style);
    },
  );
}

/// A repeating controller, paused when motion is off. [builder] gets the time (0 to 1) in the cycle.
class Loop extends StatefulWidget {
  const Loop({super.key, required this.period, required this.builder, this.child, this.still = .5});

  final Duration period;
  final Widget Function(BuildContext context, double t, Widget? child) builder;
  final Widget? child;

  /// The time shown when motion is off.
  final double still;

  @override
  State<Loop> createState() => _LoopState();
}

class _LoopState extends State<Loop> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.period);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (motionOn(context)) {
      if (!_c.isAnimating) _c.repeat();
    } else {
      _c.stop();
      _c.value = widget.still;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _c,
    child: widget.child,
    builder: (context, child) => widget.builder(context, _c.value, child),
  );
}
