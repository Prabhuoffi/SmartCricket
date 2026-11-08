import 'package:flutter/material.dart';

import '../data/api_client.dart';
import '../data/session_store.dart';
import '../ui/app_theme.dart';
import '../ui/brand.dart';

class CheckInScreen extends StatefulWidget {
  const CheckInScreen({
    super.key,
    required this.player,
    required this.token,
    required this.client,
    required this.store,
    required this.onReady,
    this.onHistory,
    required this.onLogout,
  });

  final PlayerProfile player;
  final String token;
  final ApiClient client;
  final SessionStore store;
  final VoidCallback onReady;
  final VoidCallback? onHistory;
  final VoidCallback onLogout;

  @override
  State<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends State<CheckInScreen> {
  String _soreness = 'none';
  int _feeling = 3;
  bool _busy = false;
  bool _restSaved = false;
  String? _error;

  Future<void> _submit() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final today = await widget.client.checkIn(
        widget.token,
        soreness: _soreness,
        feeling: _feeling,
      );
      if (!mounted) return;
      if (_soreness == 'stop' || today['rest_day'] == true) {
        setState(() => _restSaved = true);
      } else {
        widget.onReady();
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not save your check-in. Try again.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final firstName = widget.player.name.split(' ').first;
    return Scaffold(
      appBar: AppBar(
        title: const CricketBrand(compact: true),
        actions: [
          if (widget.onHistory != null)
            IconButton(
              onPressed: widget.onHistory,
              icon: const Icon(Icons.history_rounded),
              tooltip: 'Live history',
            ),
          TextButton(
            onPressed: _busy
                ? null
                : () async {
                    await widget.store.clear();
                    widget.onLogout();
                  },
            child: const Text('Sign out'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    key: const Key('checkin-scroll'),
                    padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(22),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                CricketColors.night,
                                CricketColors.green,
                              ],
                            ),
                            borderRadius: BorderRadius.circular(24),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Row(
                                children: [
                                  Icon(
                                    Icons.radio_button_checked,
                                    color: CricketColors.red,
                                    size: 12,
                                  ),
                                  SizedBox(width: 8),
                                  Text(
                                    'LIVE ANALYSIS',
                                    style: TextStyle(
                                      color: CricketColors.mint,
                                      fontSize: 11,
                                      fontWeight: FontWeight.w800,
                                      letterSpacing: 1.5,
                                    ),
                                  ),
                                  Spacer(),
                                  Icon(
                                    Icons.videocam_outlined,
                                    color: CricketColors.cream,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 17),
                              Text(
                                'READY FOR THE NETS?',
                                style: CricketFonts.heading(
                                  30,
                                  color: CricketColors.cream,
                                ),
                              ),
                              const SizedBox(height: 9),
                              Text(
                                'Welcome back, $firstName. Two quick answers, then your live camera opens.',
                                style: const TextStyle(
                                  color: CricketColors.mutedLight,
                                  fontSize: 13,
                                  height: 1.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 20),
                        if (_restSaved)
                          _RecoveryCard(
                            onChange: () => setState(() => _restSaved = false),
                          )
                        else ...[
                          const Row(
                            children: [
                              Expanded(
                                child: Text(
                                  'Quick coach check-in',
                                  style: TextStyle(
                                    fontSize: 19,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                              Text(
                                '1 OF 2',
                                style: TextStyle(
                                  color: CricketColors.red,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: 1.4,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(18),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: CricketColors.line),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Any soreness today?',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 5),
                                const Text(
                                  'Your answer shapes today’s practice.',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: CricketColors.muted,
                                  ),
                                ),
                                const SizedBox(height: 14),
                                Row(
                                  children: [
                                    _Choice(
                                      label: 'None',
                                      keyValue: 'soreness-none',
                                      selected: _soreness == 'none',
                                      enabled: !_busy,
                                      onTap: () =>
                                          setState(() => _soreness = 'none'),
                                    ),
                                    const SizedBox(width: 8),
                                    _Choice(
                                      label: 'A little',
                                      keyValue: 'soreness-mild',
                                      selected: _soreness == 'mild',
                                      enabled: !_busy,
                                      onTap: () =>
                                          setState(() => _soreness = 'mild'),
                                    ),
                                    const SizedBox(width: 8),
                                    _Choice(
                                      label: 'Need rest',
                                      keyValue: 'soreness-stop',
                                      selected: _soreness == 'stop',
                                      enabled: !_busy,
                                      onTap: () =>
                                          setState(() => _soreness = 'stop'),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 22),
                                const Divider(height: 1),
                                const SizedBox(height: 20),
                                const Text(
                                  'How is your energy?',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 5),
                                const Text(
                                  'Choose a number from 1 to 5.',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: CricketColors.muted,
                                  ),
                                ),
                                const SizedBox(height: 14),
                                Row(
                                  children: List.generate(5, (index) {
                                    final value = index + 1;
                                    return _Choice(
                                      label: '$value',
                                      keyValue: 'energy-$value',
                                      selected: _feeling == value,
                                      enabled: !_busy,
                                      marginRight: index == 4 ? 0 : 8,
                                      onTap: () =>
                                          setState(() => _feeling = value),
                                    );
                                  }),
                                ),
                                const SizedBox(height: 7),
                                const Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text('LOW', style: _scaleLabel),
                                    Text('GREAT', style: _scaleLabel),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          if (_soreness == 'stop') ...[
                            const SizedBox(height: 12),
                            const _Note(
                              text:
                                  'Rest comes first today. Your coach will pause live practice.',
                            ),
                          ],
                          if (_error != null) ...[
                            const SizedBox(height: 12),
                            _Note(text: _error!, error: true),
                          ],
                        ],
                      ],
                    ),
                  ),
                ),
                if (!_restSaved)
                  Container(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
                    decoration: const BoxDecoration(
                      color: CricketColors.cream,
                      border: Border(
                        top: BorderSide(color: CricketColors.line),
                      ),
                    ),
                    child: Column(
                      children: [
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            key: const Key('checkin-continue'),
                            onPressed: _busy ? null : _submit,
                            iconAlignment: IconAlignment.end,
                            icon: _busy
                                ? const SizedBox.square(
                                    dimension: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : Icon(
                                    _soreness == 'stop'
                                        ? Icons.favorite_outline_rounded
                                        : Icons.videocam_rounded,
                                  ),
                            label: Text(
                              _busy
                                  ? 'Saving check-in…'
                                  : _soreness == 'stop'
                                  ? 'Save recovery check-in'
                                  : 'Continue to live camera',
                            ),
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          '2 OF 2  •  Live camera and coaching next',
                          style: TextStyle(
                            color: CricketColors.muted,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
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
    );
  }
}

const _scaleLabel = TextStyle(
  color: CricketColors.muted,
  fontSize: 10,
  fontWeight: FontWeight.w800,
  letterSpacing: 1,
);

class _Choice extends StatelessWidget {
  const _Choice({
    required this.label,
    required this.keyValue,
    required this.selected,
    required this.enabled,
    required this.onTap,
    this.marginRight = 0,
  });
  final String label;
  final String keyValue;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;
  final double marginRight;

  @override
  Widget build(BuildContext context) => Expanded(
    child: Padding(
      padding: EdgeInsets.only(right: marginRight),
      child: Semantics(
        button: true,
        selected: selected,
        child: InkWell(
          key: Key(keyValue),
          onTap: enabled ? onTap : null,
          borderRadius: BorderRadius.circular(13),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 160),
            height: 48,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: selected ? CricketColors.green : CricketColors.cream,
              borderRadius: BorderRadius.circular(13),
              border: Border.all(
                color: selected ? CricketColors.green : CricketColors.line,
              ),
            ),
            child: Text(
              label,
              maxLines: 1,
              style: TextStyle(
                color: selected ? Colors.white : CricketColors.ink,
                fontSize: keyValue.startsWith('energy') ? 18 : 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class _Note extends StatelessWidget {
  const _Note({required this.text, this.error = false});
  final String text;
  final bool error;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: error ? const Color(0xFFFFE8E9) : const Color(0xFFE6F0E8),
      borderRadius: BorderRadius.circular(13),
    ),
    child: Row(
      children: [
        Icon(
          error ? Icons.error_outline_rounded : Icons.favorite_outline_rounded,
          color: error ? CricketColors.red : CricketColors.green,
          size: 19,
        ),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: error ? CricketColors.red : CricketColors.green,
              fontSize: 12,
              height: 1.4,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}

class _RecoveryCard extends StatelessWidget {
  const _RecoveryCard({required this.onChange});
  final VoidCallback onChange;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: CricketColors.line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.favorite_rounded, color: CricketColors.red, size: 30),
        const SizedBox(height: 14),
        const Text(
          'Recovery comes first',
          style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          'Your check-in is saved. Take a rest day and return when you feel ready. Live practice is paused for today.',
          style: TextStyle(
            color: CricketColors.muted,
            height: 1.55,
            fontSize: 14,
          ),
        ),
        const SizedBox(height: 20),
        OutlinedButton.icon(
          onPressed: onChange,
          icon: const Icon(Icons.edit_outlined),
          label: const Text('Update check-in'),
        ),
      ],
    ),
  );
}
