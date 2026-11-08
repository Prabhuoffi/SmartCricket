import 'dart:typed_data';

/// Measurements and one automatically chosen camera frame from a live session.
class SessionReport {
  const SessionReport({
    required this.durationSeconds,
    required this.reps,
    required this.saved,
    this.leftKnee,
    this.rightKnee,
    this.shoulderTilt,
    this.cue,
    this.saveError,
    this.bestMomentBytes,
    this.momentSaved = false,
    this.momentSaveError,
    this.sessionId,
  });

  final int durationSeconds;
  final int reps;
  final bool saved;
  final double? leftKnee;
  final double? rightKnee;
  final double? shoulderTilt;
  final String? cue;
  final String? saveError;
  final Uint8List? bestMomentBytes;
  final bool momentSaved;
  final String? momentSaveError;
  final int? sessionId;

  String get durationLabel {
    final minutes = durationSeconds ~/ 60;
    final seconds = durationSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }
}
