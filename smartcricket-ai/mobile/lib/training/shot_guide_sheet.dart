import 'dart:async';

import 'package:flutter/material.dart';

import '../ui/app_theme.dart';
import 'shot_guide.dart';

class ShotGuideSheet extends StatefulWidget {
  const ShotGuideSheet({
    super.key,
    required this.guides,
    required this.onNarrate,
    this.initial,
  });

  final List<ShotGuide> guides;
  final ShotGuide? initial;
  final ValueChanged<ShotGuide> onNarrate;

  @override
  State<ShotGuideSheet> createState() => _ShotGuideSheetState();
}

class _ShotGuideSheetState extends State<ShotGuideSheet> {
  late ShotGuide? _guide = widget.initial;
  final _search = TextEditingController();
  Timer? _timer;
  int _phase = 0;
  String? _message;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 1800), (_) {
      if (mounted && MediaQuery.disableAnimationsOf(context) == false) {
        setState(() => _phase = (_phase + 1) % 3);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _choose(ShotGuide guide) {
    setState(() {
      _guide = guide;
      _phase = 0;
      _message = null;
    });
    widget.onNarrate(guide);
  }

  void _find() {
    final found = ShotGuides.match(_search.text, widget.guides);
    if (found != null) {
      _choose(found);
    } else {
      setState(
        () => _message =
            'No illustrated guide for that name yet. Try hook, front foot, pull or cover drive.',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final guide = _guide;
    return SafeArea(
      top: false,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * .78,
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.sports_cricket_rounded,
                    color: CricketColors.mint,
                  ),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'SHOT GUIDE',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close_rounded, color: Colors.white),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Ask “how do I play a hook shot?” or search by name.',
                style: TextStyle(color: CricketColors.mutedLight, fontSize: 13),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _search,
                      textInputAction: TextInputAction.search,
                      onSubmitted: (_) => _find(),
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        hintText: 'Front foot, hook, cover drive…',
                        hintStyle: const TextStyle(
                          color: CricketColors.mutedLight,
                        ),
                        filled: true,
                        fillColor: const Color(0xFF164A36),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(onPressed: _find, child: const Text('Show')),
                ],
              ),
              if (_message != null) ...[
                const SizedBox(height: 10),
                Text(
                  _message!,
                  style: const TextStyle(color: CricketColors.cream),
                ),
              ],
              const SizedBox(height: 12),
              if (guide == null)
                Wrap(
                  spacing: 7,
                  runSpacing: 6,
                  children: widget.guides
                      .map(
                        (item) => ActionChip(
                          label: Text(item.name),
                          onPressed: () => _choose(item),
                        ),
                      )
                      .toList(),
                )
              else ...[
                Text(
                  guide.name,
                  style: CricketFonts.heading(28, color: CricketColors.cream),
                ),
                const SizedBox(height: 4),
                Text(
                  guide.when,
                  style: const TextStyle(
                    color: CricketColors.mutedLight,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  height: 180,
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFF06271C),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: CustomPaint(
                    painter: _ShotFigure(guide.family, _phase),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  '${['SET UP', 'MOVE', 'FINISH'][_phase]} · ${guide.steps[_phase]}',
                  style: const TextStyle(
                    color: CricketColors.cream,
                    fontWeight: FontWeight.w700,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 5),
                const Text(
                  'Illustration only. Watch the ball and practise slowly without a ball first.',
                  style: TextStyle(
                    color: CricketColors.mutedLight,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () => widget.onNarrate(guide),
                  icon: const Icon(Icons.volume_up_rounded),
                  label: const Text('Hear steps again'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ShotFigure extends CustomPainter {
  const _ShotFigure(this.family, this.phase);
  final String family;
  final int phase;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.translate((size.width - 240 * size.height / 160) / 2, 0);
    canvas.scale(size.height / 160);
    final body = Paint()
      ..color = CricketColors.cream
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round;
    final arms = Paint()
      ..color = CricketColors.mint
      ..strokeWidth = 7
      ..strokeCap = StrokeCap.round;
    final bat = Paint()
      ..color = const Color(0xFFF5C542)
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round;
    final back = family == 'cross' || family == 'high';
    final front = phase == 0
        ? 90.0
        : back
        ? 103.0
        : family == 'low'
        ? 70.0
        : 67.0;
    final headY = family == 'low' && phase > 0 ? 50.0 : 38.0;
    final hipY = family == 'low' && phase > 0 ? 104.0 : 93.0;
    final hand = phase == 0
        ? const Offset(82, 45)
        : phase == 1
        ? family == 'cross'
              ? const Offset(150, 78)
              : family == 'high'
              ? const Offset(155, 49)
              : family == 'low'
              ? const Offset(79, 112)
              : const Offset(93, 98)
        : family == 'cross'
        ? const Offset(178, 62)
        : family == 'high'
        ? const Offset(178, 27)
        : family == 'low'
        ? const Offset(168, 98)
        : const Offset(156, 40);
    final tip = phase == 0
        ? const Offset(67, 12)
        : phase == 1
        ? family == 'cross'
              ? const Offset(186, 75)
              : family == 'high'
              ? const Offset(190, 27)
              : family == 'low'
              ? const Offset(48, 116)
              : const Offset(81, 132)
        : family == 'low'
        ? const Offset(204, 81)
        : const Offset(190, 12);
    canvas.drawLine(
      const Offset(25, 141),
      const Offset(216, 141),
      Paint()
        ..color = const Color(0xFF486E5B)
        ..strokeWidth = 2,
    );
    canvas.drawCircle(Offset(113, headY), 12, body);
    canvas.drawLine(Offset(113, headY + 13), Offset(116, hipY), body);
    canvas.drawLine(Offset(116, hipY), Offset(front, 140), body);
    canvas.drawLine(Offset(116, hipY), const Offset(139, 140), body);
    canvas.drawLine(Offset(112, headY + 25), hand, arms);
    canvas.drawLine(Offset(123, headY + 29), hand + const Offset(3, 3), arms);
    canvas.drawLine(hand, tip, bat);
    canvas.drawCircle(hand, 5, Paint()..color = Colors.white);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _ShotFigure oldDelegate) =>
      family != oldDelegate.family || phase != oldDelegate.phase;
}
