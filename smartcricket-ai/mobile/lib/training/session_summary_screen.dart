import 'package:flutter/material.dart';

import '../data/api_client.dart';
import '../ui/app_theme.dart';
import '../ui/brand.dart';
import 'session_report.dart';

class SessionSummaryScreen extends StatelessWidget {
  const SessionSummaryScreen({
    super.key,
    required this.player,
    required this.report,
    this.client,
    this.token,
    required this.onPractiseAgain,
    this.onHistory,
    required this.onLogout,
  });

  final PlayerProfile player;
  final SessionReport? report;
  final ApiClient? client;
  final String? token;
  final VoidCallback onPractiseAgain;
  final VoidCallback? onHistory;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final data =
        report ??
        const SessionReport(durationSeconds: 0, reps: 0, saved: false);
    var momentSaved = data.momentSaved;
    var retryingMoment = false;
    String? momentError = data.momentSaveError;
    final firstName = player.name.split(' ').first;
    return Scaffold(
      appBar: AppBar(
        title: const CricketBrand(compact: true),
        automaticallyImplyLeading: false,
        actions: [
          TextButton(onPressed: onLogout, child: const Text('Sign out')),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(24),
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [CricketColors.night, CricketColors.green],
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              data.saved
                                  ? Icons.check_circle_rounded
                                  : Icons.info_outline_rounded,
                              color: data.saved
                                  ? CricketColors.mint
                                  : CricketColors.cream,
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              data.saved ? 'SESSION SAVED' : 'SESSION ENDED',
                              style: const TextStyle(
                                color: CricketColors.mint,
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 18),
                        Text(
                          'LIVE SESSION RECAP',
                          style: CricketFonts.heading(
                            29,
                            color: CricketColors.cream,
                          ),
                        ),
                        const SizedBox(height: 9),
                        Text(
                          'Nice work, $firstName. Here is what your camera measured today.',
                          style: const TextStyle(
                            color: CricketColors.mutedLight,
                            fontSize: 13,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (!data.saved) ...[
                    const SizedBox(height: 12),
                    _Note(
                      text: data.saveError ?? 'This session was not saved.',
                    ),
                  ],
                  if (data.bestMomentBytes != null) ...[
                    const SizedBox(height: 18),
                    StatefulBuilder(
                      builder: (context, updateMoment) => Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(22),
                          border: Border.all(color: CricketColors.line),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(15),
                              child: AspectRatio(
                                aspectRatio: 4 / 3,
                                child: Image.memory(
                                  data.bestMomentBytes!,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, _, _) => const ColoredBox(
                                    color: CricketColors.night,
                                    child: Center(
                                      child: Icon(
                                        Icons.image_not_supported_outlined,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                const Icon(
                                  Icons.auto_awesome_rounded,
                                  color: CricketColors.green,
                                  size: 18,
                                ),
                                const SizedBox(width: 7),
                                const Expanded(
                                  child: Text(
                                    'Your tracked shot moment',
                                    style: TextStyle(
                                      fontWeight: FontWeight.w800,
                                      fontSize: 16,
                                    ),
                                  ),
                                ),
                                const Text(
                                  'SHOT',
                                  style: TextStyle(
                                    color: CricketColors.green,
                                    fontWeight: FontWeight.w800,
                                    fontSize: 11,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 5),
                            Text(
                              momentSaved
                                  ? 'Captured during clear arm movement and saved with this session.'
                                  : momentError ??
                                        'Captured on this phone. The image was not saved.',
                              style: TextStyle(
                                color: momentSaved
                                    ? CricketColors.muted
                                    : CricketColors.red,
                                fontSize: 12,
                                height: 1.4,
                              ),
                            ),
                            if (!momentSaved &&
                                data.sessionId != null &&
                                client != null &&
                                token != null) ...[
                              const SizedBox(height: 10),
                              OutlinedButton.icon(
                                onPressed: retryingMoment
                                    ? null
                                    : () async {
                                        updateMoment(
                                          () => retryingMoment = true,
                                        );
                                        try {
                                          await client!.saveBestMoment(
                                            token!,
                                            data.sessionId!,
                                            data.bestMomentBytes!,
                                            metric: 'shot_motion',
                                          );
                                          if (!context.mounted) return;
                                          updateMoment(() {
                                            momentSaved = true;
                                            momentError = null;
                                            retryingMoment = false;
                                          });
                                        } on ApiException catch (error) {
                                          if (!context.mounted) return;
                                          updateMoment(() {
                                            momentError = error.message;
                                            retryingMoment = false;
                                          });
                                        } catch (_) {
                                          if (!context.mounted) return;
                                          updateMoment(() {
                                            momentError =
                                                'The image still could not be saved.';
                                            retryingMoment = false;
                                          });
                                        }
                                      },
                                icon: retryingMoment
                                    ? const SizedBox.square(
                                        dimension: 16,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : const Icon(Icons.cloud_upload_outlined),
                                label: Text(
                                  retryingMoment
                                      ? 'Saving image…'
                                      : 'Retry image save',
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ],
                  if (data.saved && data.bestMomentBytes == null) ...[
                    const SizedBox(height: 18),
                    const Text(
                      'No shot moment was captured. Next time, keep your wrists and whole body in view during the swing.',
                      style: TextStyle(
                        color: CricketColors.muted,
                        fontSize: 12,
                        height: 1.45,
                      ),
                    ),
                  ],
                  const SizedBox(height: 20),
                  const Text('YOUR NUMBERS', style: CricketFonts.eyebrow),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          icon: Icons.timer_outlined,
                          value: data.durationLabel,
                          label: 'DURATION',
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _StatCard(
                          icon: Icons.repeat_rounded,
                          value: '${data.reps}',
                          label: 'KNEE BENDS',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
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
                          'Camera feedback',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 7),
                        const Text(
                          'Last clear full-body frame',
                          style: TextStyle(
                            fontSize: 12,
                            color: CricketColors.muted,
                          ),
                        ),
                        const SizedBox(height: 17),
                        if (data.leftKnee == null &&
                            data.rightKnee == null &&
                            data.shoulderTilt == null)
                          const Text(
                            'No full-body pose was captured. Next time, place the phone 2 to 3 metres away, side-on, with your whole body in view.',
                            style: TextStyle(
                              fontSize: 13,
                              color: CricketColors.muted,
                              height: 1.5,
                            ),
                          )
                        else ...[
                          if (data.leftKnee != null)
                            _MeasureRow(
                              label: 'Left knee',
                              value: data.leftKnee!,
                            ),
                          if (data.rightKnee != null)
                            _MeasureRow(
                              label: 'Right knee',
                              value: data.rightKnee!,
                            ),
                          if (data.shoulderTilt != null)
                            _MeasureRow(
                              label: 'Shoulder line',
                              value: data.shoulderTilt!,
                            ),
                          const SizedBox(height: 8),
                          const Text(
                            'Angles are 2D estimates from one camera view.',
                            style: TextStyle(
                              fontSize: 11,
                              color: CricketColors.muted,
                              height: 1.45,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: onPractiseAgain,
                      iconAlignment: IconAlignment.end,
                      icon: const Icon(Icons.videocam_rounded),
                      label: const Text('Start another session'),
                    ),
                  ),
                  const SizedBox(height: 10),
                  if (onHistory != null) ...[
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: onHistory,
                        icon: const Icon(Icons.history_rounded),
                        label: const Text('View live history'),
                      ),
                    ),
                    const SizedBox(height: 10),
                  ],
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: onLogout,
                      child: const Text('Sign out'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.value,
    required this.label,
  });
  final IconData icon;
  final String value;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(17),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: CricketColors.line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: CricketColors.green, size: 20),
        const SizedBox(height: 13),
        Text(value, style: CricketFonts.heading(30)),
        const SizedBox(height: 3),
        Text(
          label,
          style: const TextStyle(
            color: CricketColors.muted,
            fontSize: 10,
            fontWeight: FontWeight.w800,
            letterSpacing: 1,
          ),
        ),
      ],
    ),
  );
}

class _MeasureRow extends StatelessWidget {
  const _MeasureRow({required this.label, required this.value});
  final String label;
  final double value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 11),
    child: Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 13, color: CricketColors.muted),
          ),
        ),
        Text(
          '${value.round()}°',
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: CricketColors.green,
          ),
        ),
      ],
    ),
  );
}

class _Note extends StatelessWidget {
  const _Note({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: const Color(0xFFFFE8E9),
      borderRadius: BorderRadius.circular(13),
    ),
    child: Row(
      children: [
        const Icon(
          Icons.error_outline_rounded,
          color: CricketColors.red,
          size: 19,
        ),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: CricketColors.red,
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ),
      ],
    ),
  );
}
