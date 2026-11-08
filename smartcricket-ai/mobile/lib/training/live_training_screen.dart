import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:wakelock_plus/wakelock_plus.dart';

import '../data/api_client.dart';
import '../ui/app_theme.dart';
import '../ui/motion.dart';
import 'pose_metrics.dart';
import 'session_report.dart';
import 'shot_guide.dart';
import 'shot_guide_sheet.dart';
import 'shot_motion_tracker.dart';

class LiveTrainingScreen extends StatefulWidget {
  const LiveTrainingScreen({
    super.key,
    required this.player,
    required this.token,
    required this.client,
    required this.onFinish,
    required this.onBack,
    required this.onLogout,
  });

  final PlayerProfile player;
  final String token;
  final ApiClient client;
  final ValueChanged<SessionReport> onFinish;
  final VoidCallback onBack;
  final VoidCallback onLogout;

  @override
  State<LiveTrainingScreen> createState() => _LiveTrainingScreenState();
}

class _LiveTrainingScreenState extends State<LiveTrainingScreen>
    with WidgetsBindingObserver {
  static final stt.SpeechToText _speech = stt.SpeechToText();
  static _LiveTrainingScreenState? _activeSpeechScreen;
  CameraController? _cam;
  PoseDetector? _detector;
  final FlutterTts _tts = FlutterTts();
  late final Future<void> _ttsReady;
  final KneeBendCounter _counter = KneeBendCounter();
  final ShotMotionTracker _shotTracker = ShotMotionTracker();
  late final Future<List<ShotGuide>> _shotGuidesReady;
  List<ShotGuide> _shotGuides = const [];
  bool _guideOpen = false;

  bool _paused = false;
  bool _camReady = false;
  String? _camError;
  bool _framesReceived = false;
  Timer? _cameraWatchdog;
  bool _processing = false;
  bool _saving = false;
  bool _voiceOn = true;
  bool _voiceListening = false;
  String _commandFeedback =
      'Tap mic: ask for a shot, pause, resume, reset or finish';
  String? _bestMomentPath;
  double _bestMomentScore = double.negativeInfinity;
  int _momentCaptures = 0;
  DateTime? _lastMomentAttempt;
  Future<void>? _captureTask;
  bool _momentFlash = false;
  Timer? _momentFlashTimer;
  int _lastReps = 0;
  int? _repPulse;
  Timer? _repPulseTimer;

  PoseMetrics? _metrics;
  PoseMetrics? _lastValidMetrics;
  List<PoseLandmark> _landmarks = [];
  Size _imageSize = Size.zero;
  CameraLensDirection _lensDir = CameraLensDirection.back;

  final _stopwatch = Stopwatch();
  String _elapsed = '0:00';
  Timer? _clockTimer;

  String? _lastCue;
  DateTime? _lastCueAt;

  @override
  void initState() {
    super.initState();
    _activeSpeechScreen = this;
    WidgetsBinding.instance.addObserver(this);
    _ttsReady = _initTts();
    _shotGuidesReady = ShotGuides.load().then((guides) {
      _shotGuides = guides;
      return guides;
    });
    _initDetector();
    _initCamera();
    WakelockPlus.enable();
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  }

  @override
  void dispose() {
    if (identical(_activeSpeechScreen, this)) _activeSpeechScreen = null;
    WidgetsBinding.instance.removeObserver(this);
    _clockTimer?.cancel();
    _cameraWatchdog?.cancel();
    _momentFlashTimer?.cancel();
    _repPulseTimer?.cancel();
    final momentPath = _bestMomentPath;
    if (momentPath != null) unawaited(_removeMomentFile(momentPath));
    _cam?.stopImageStream().catchError((_) {});
    _cam?.dispose();
    _detector?.close();
    _tts.stop();
    _speech.cancel();
    WakelockPlus.disable();
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) _pauseSession();
    if (state == AppLifecycleState.resumed && !_paused) _resumeSession();
  }

  Future<void> _initTts() async {
    try {
      final available = await _tts.isLanguageAvailable('en-IN');
      await _tts.setLanguage(available == 1 ? 'en-IN' : 'en-US');
      await _tts.setSpeechRate(0.48);
      await _tts.setVolume(1);
    } catch (_) {
      // Training continues with visible cues if speech is unavailable.
    }
  }

  void _initDetector() {
    _detector = PoseDetector(
      options: PoseDetectorOptions(mode: PoseDetectionMode.stream),
    );
  }

  Future<void> _initCamera() async {
    List<CameraDescription> cameras;
    try {
      cameras = await availableCameras();
    } catch (_) {
      if (mounted) {
        setState(
          () => _camError =
              'Camera unavailable. Check camera permission and try again.',
        );
      }
      return;
    }
    if (!mounted) return;
    if (cameras.isEmpty) {
      setState(() => _camError = 'No cameras found on this device.');
      return;
    }
    final cam = cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.back,
      orElse: () => cameras.first,
    );
    _lensDir = cam.lensDirection;
    final controller = CameraController(
      cam,
      ResolutionPreset.medium,
      imageFormatGroup: Platform.isAndroid
          ? ImageFormatGroup.nv21
          : ImageFormatGroup.bgra8888,
      enableAudio: false,
    );
    _cam = controller;
    try {
      await controller.initialize();
      if (!mounted) return;
      await controller.startImageStream(_onFrame);
      setState(() => _camReady = true);
      _cameraWatchdog?.cancel();
      _cameraWatchdog = Timer(const Duration(seconds: 5), () {
        if (!mounted || _paused || _framesReceived) return;
        _stopwatch.stop();
        _clockTimer?.cancel();
        setState(
          () => _camError =
              'The camera opened, but no video frames arrived. Tap Retry camera.',
        );
      });
      _stopwatch.start();
      _speak('Camera ready. Step back until your whole body is visible.');
      _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted && !_paused) {
          final s = _stopwatch.elapsed.inSeconds;
          setState(
            () =>
                _elapsed = '${s ~/ 60}:${(s % 60).toString().padLeft(2, '0')}',
          );
        }
      });
    } on CameraException catch (e) {
      if (mounted) {
        setState(() => _camError = e.description ?? 'Camera unavailable.');
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _camError =
              'Could not open the camera. Check permission and try again.',
        );
      }
    }
  }

  void _onFrame(CameraImage image) async {
    if (image.planes.isEmpty || image.planes.first.bytes.isEmpty) return;
    _framesReceived = true;
    _cameraWatchdog?.cancel();
    if (_paused || _processing || _detector == null) return;
    _processing = true;
    try {
      final cam = _cam;
      if (cam == null || !cam.value.isInitialized) return;

      final rotation = _rotationFromSensor(cam.description.sensorOrientation);
      final inputImage = _buildInputImage(image, rotation);
      if (inputImage == null) return;

      final poses = await _detector!.processImage(inputImage);
      if (!mounted || cam != _cam) return;

      if (poses.isEmpty) {
        setState(() {
          _landmarks = [];
          _metrics = null;
          _imageSize = Size.zero;
        });
        _counter.clearContinuity();
        _shotTracker.reset();
        return;
      }

      final pose = poses.first;
      final points = _landmarksToMap(pose.landmarks);
      final metrics = PoseMetrics.fromPoints(points);
      final shotScore = metrics.hasBody
          ? _shotTracker.update(points, _stopwatch.elapsed)
          : null;
      if (!metrics.hasBody) _shotTracker.reset();

      _counter.update(
        kneeAngle: metrics.mostBentKnee,
        elapsed: _stopwatch.elapsed,
      );
      if (_counter.reps > _lastReps) {
        _lastReps = _counter.reps;
        _repPulse = _lastReps;
        _repPulseTimer?.cancel();
        _repPulseTimer = Timer(const Duration(milliseconds: 1200), () {
          if (mounted) setState(() => _repPulse = null);
        });
        HapticFeedback.lightImpact();
        _speak('Rep $_lastReps');
      }

      setState(() {
        _landmarks = pose.landmarks.values.toList();
        _metrics = metrics;
        if (metrics.hasBody) _lastValidMetrics = metrics;
        // ML Kit reports points in the upright frame, so a 90° or 270°
        // sensor swaps the raw buffer's width and height.
        _imageSize =
            rotation == InputImageRotation.rotation90deg ||
                rotation == InputImageRotation.rotation270deg
            ? Size(image.height.toDouble(), image.width.toDouble())
            : Size(image.width.toDouble(), image.height.toDouble());
      });

      _considerBestMoment(shotScore, cam);
      _maybeSpeakCue(metrics.cue);
    } catch (_) {
      // Frame errors are non-fatal; skip this frame.
    } finally {
      _processing = false;
    }
  }

  void _speak(String cue) {
    if (!_voiceOn || _paused || _voiceListening || _guideOpen || !mounted) {
      return;
    }
    _ttsReady
        .then((_) async {
          if (!_voiceOn ||
              _paused ||
              _voiceListening ||
              _guideOpen ||
              !mounted) {
            return;
          }
          await _tts.stop();
          await _tts.speak(cue);
        })
        .catchError((_) {});
  }

  Future<void> _toggleVoiceCommands() async {
    if (_saving) return;
    if (_voiceListening) {
      await _speech.stop();
      if (mounted) setState(() => _voiceListening = false);
      return;
    }
    try {
      final available = await _speech.initialize(
        onStatus: (status) {
          final active = _activeSpeechScreen;
          if (active?.mounted == true) {
            active!.setState(() {
              active._voiceListening =
                  status == stt.SpeechToText.listeningStatus;
            });
          }
        },
        onError: (_) {
          final active = _activeSpeechScreen;
          if (active?.mounted == true) {
            active!.setState(() {
              active._voiceListening = false;
              active._commandFeedback =
                  'Voice commands unavailable. Use the buttons.';
            });
          }
        },
        options: [stt.SpeechToText.androidNoBluetooth],
      );
      if (!mounted) return;
      if (!available) {
        setState(
          () =>
              _commandFeedback = 'Voice commands unavailable. Use the buttons.',
        );
        return;
      }
      await _tts.stop();
      await _speech.listen(
        onResult: (result) {
          if (!mounted) return;
          if (result.finalResult) {
            _handleVoiceCommand(result.recognizedWords);
          } else {
            setState(
              () => _commandFeedback = 'Heard: ${result.recognizedWords}',
            );
          }
        },
        listenOptions: stt.SpeechListenOptions(
          listenFor: const Duration(seconds: 8),
          pauseFor: const Duration(seconds: 2),
        ),
      );
      if (mounted) {
        setState(() {
          _voiceListening = _speech.isListening;
          if (_voiceListening) {
            _commandFeedback =
                'Listening: ask for a shot, pause, resume, reset or finish';
          }
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _voiceListening = false;
          _commandFeedback = 'Voice commands unavailable. Use the buttons.';
        });
      }
    }
  }

  void _handleVoiceCommand(String spoken) {
    final words = spoken.toLowerCase().trim();
    if (words.isEmpty) return;
    final shot = ShotGuides.match(words, _shotGuides);
    if (shot != null ||
        RegExp(
          r'\b(how (do|can|to).*(play|hit)|show me.*(shot|stroke)|teach me.*(shot|stroke))\b',
        ).hasMatch(words)) {
      setState(() => _commandFeedback = 'Opening shot guide…');
      unawaited(_openShotGuide(spoken));
      return;
    }
    if (RegExp(r'\b(finish|finished|done|complete)\b').hasMatch(words)) {
      setState(() => _commandFeedback = 'Heard “finish” · saving session');
      _speech.stop();
      _endSession();
    } else if (RegExp(r'\b(reset|restart|zero)\b').hasMatch(words)) {
      _counter.reset();
      _lastReps = 0;
      _repPulse = null;
      setState(() => _commandFeedback = 'Heard “reset” · count cleared');
      _speak('Count reset.');
    } else if (RegExp(r'\b(pause|stop)\b').hasMatch(words)) {
      _pauseSession();
      setState(() => _commandFeedback = 'Heard “pause”');
    } else if (RegExp(r'\b(resume|start|continue)\b').hasMatch(words)) {
      final wasPaused = _paused;
      if (wasPaused) _resumeSession();
      setState(
        () => _commandFeedback = wasPaused
            ? 'Heard “resume”'
            : 'Camera is running',
      );
    } else {
      setState(
        () => _commandFeedback =
            'Heard “$spoken” · ask for a shot or try pause, resume, reset or finish',
      );
    }
  }

  Future<void> _narrateGuide(ShotGuide guide, {bool force = false}) async {
    await _narrateText(guide.spokenGuide, force: force);
  }

  Future<void> _narrateText(String words, {bool force = false}) async {
    if ((!_voiceOn && !force) || !mounted) return;
    try {
      await _ttsReady;
      await _tts.stop();
      await _tts.speak(words.replaceAll(RegExp(r'[*#]'), ' '));
    } catch (_) {}
  }

  Future<void> _openShotGuide(String? query) async {
    if (_guideOpen || !mounted) return;
    _guideOpen = true;
    try {
      if (_voiceListening) {
        await _speech.stop();
        if (mounted) setState(() => _voiceListening = false);
      }
      final guides = await _shotGuidesReady;
      if (!mounted) return;
      final name = query?.trim() ?? '';
      final selected = name.isEmpty ? null : ShotGuides.match(name, guides);
      if (name.isNotEmpty && selected == null) {
        setState(() => _commandFeedback = 'Asking the coach about “$name”…');
        try {
          final answer = await widget.client.askCoach(
            widget.token,
            'How do I play the cricket shot called $name? Explain the footwork, bat path and a safe shadow-practice drill.',
          );
          if (!mounted) return;
          final route = showModalBottomSheet<void>(
            context: context,
            isScrollControlled: true,
            backgroundColor: CricketColors.night,
            builder: (context) => SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: CricketFonts.heading(
                          27,
                          color: CricketColors.cream,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        answer,
                        style: const TextStyle(
                          color: CricketColors.cream,
                          height: 1.5,
                        ),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Text coaching for this name. No movement illustration is available yet.',
                        style: TextStyle(
                          color: CricketColors.mutedLight,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
          unawaited(
            _narrateText(
              answer.length > 650 ? answer.substring(0, 650) : answer,
            ),
          );
          await route;
          return;
        } on ApiException catch (error) {
          if (mounted) setState(() => _commandFeedback = error.message);
          return;
        }
      }
      final route = showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: CricketColors.night,
        builder: (context) => ShotGuideSheet(
          guides: guides,
          initial: selected,
          onNarrate: (guide) => unawaited(_narrateGuide(guide, force: true)),
        ),
      );
      if (selected != null) unawaited(_narrateGuide(selected));
      await route;
    } catch (_) {
      if (mounted) {
        setState(
          () => _commandFeedback = 'Shot guide is unavailable. Try again.',
        );
      }
    } finally {
      _guideOpen = false;
      await _tts.stop();
    }
  }

  void _maybeSpeakCue(String cue) {
    if (cue.startsWith('Body in view')) return;
    final now = DateTime.now();
    if (cue == _lastCue &&
        _lastCueAt != null &&
        now.difference(_lastCueAt!) < const Duration(seconds: 8)) {
      return;
    }
    _lastCue = cue;
    _lastCueAt = now;
    _speak(cue);
  }

  void _considerBestMoment(double? score, CameraController camera) {
    if (_paused ||
        _saving ||
        score == null ||
        _captureTask != null ||
        _momentCaptures >= 5) {
      return;
    }
    if (score <= _bestMomentScore + 2) return;
    final now = DateTime.now();
    if (_lastMomentAttempt != null &&
        now.difference(_lastMomentAttempt!) < const Duration(seconds: 3)) {
      return;
    }
    _lastMomentAttempt = now;
    _captureTask = _captureMoment(camera, score);
  }

  Future<void> _captureMoment(CameraController camera, double score) async {
    try {
      final picture = await camera.takePicture();
      if (!mounted || camera != _cam || _saving) {
        await _removeMomentFile(picture.path);
        return;
      }
      final old = _bestMomentPath;
      _bestMomentPath = picture.path;
      _bestMomentScore = score;
      _momentCaptures++;
      if (old != null) await _removeMomentFile(old);
      _momentFlashTimer?.cancel();
      setState(() => _momentFlash = true);
      _momentFlashTimer = Timer(const Duration(milliseconds: 1700), () {
        if (mounted) setState(() => _momentFlash = false);
      });
    } catch (_) {
      // A still capture can fail on some devices while analysis continues.
    } finally {
      _captureTask = null;
    }
  }

  Future<void> _removeMomentFile(String path) async {
    try {
      await File(path).delete();
    } catch (_) {}
  }

  Future<void> _restartCamera() async {
    _cameraWatchdog?.cancel();
    _clockTimer?.cancel();
    _stopwatch.stop();
    _stopwatch.reset();
    final previous = _cam;
    _cam = null;
    if (previous != null) {
      try {
        if (previous.value.isStreamingImages) await previous.stopImageStream();
      } catch (_) {}
      try {
        await previous.dispose();
      } catch (_) {}
    }
    if (!mounted) return;
    _counter.reset();
    _lastReps = 0;
    _repPulse = null;
    final momentPath = _bestMomentPath;
    _bestMomentPath = null;
    if (momentPath != null) await _removeMomentFile(momentPath);
    _shotTracker.reset();
    _bestMomentScore = double.negativeInfinity;
    _momentCaptures = 0;
    setState(() {
      _camError = null;
      _camReady = false;
      _framesReceived = false;
      _elapsed = '0:00';
      _metrics = null;
      _landmarks = [];
      _imageSize = Size.zero;
      _paused = false;
    });
    await _initCamera();
  }

  void _pauseSession() {
    if (_paused) return;
    _stopwatch.stop();
    _counter.clearContinuity();
    _shotTracker.reset();
    _cam?.stopImageStream().catchError((_) {});
    _tts.stop();
    setState(() => _paused = true);
  }

  Future<void> _resumeSession() async {
    if (!_paused) return;
    _stopwatch.start();
    setState(() => _paused = false);
    _cam?.startImageStream(_onFrame).catchError((_) {});
  }

  Future<void> _endSession() async {
    if (_saving) return;
    if (_voiceListening) await _speech.stop();
    _pauseSession();
    await _captureTask;
    if (!mounted) return;
    setState(() => _saving = true);
    final durationSeconds = _stopwatch.elapsed.inSeconds;
    final metrics = _lastValidMetrics;
    bool saved = false;
    int? sessionId;
    String? saveError;
    String? momentSaveError;
    bool momentSaved = false;
    Uint8List? momentBytes;
    final momentPath = _bestMomentPath;
    if (momentPath != null) {
      try {
        momentBytes = await File(momentPath).readAsBytes();
      } catch (_) {
        momentSaveError = 'The captured frame could not be read.';
      }
      await _removeMomentFile(momentPath);
      _bestMomentPath = null;
    }
    try {
      if (durationSeconds < 1) {
        saveError = 'The session was too short to save.';
      } else {
        sessionId = await widget.client.saveLive(
          widget.token,
          durationSeconds: durationSeconds,
          reps: _counter.reps,
          stats: {
            'left_knee': metrics?.leftKnee,
            'right_knee': metrics?.rightKnee,
            'left_elbow': metrics?.leftElbow,
            'right_elbow': metrics?.rightElbow,
            'shoulder_tilt': metrics?.shoulderTilt,
            'visible_points': metrics?.visiblePoints,
            'best_action': momentBytes == null ? null : 'tracked_arm_motion',
          },
        );
        saved = true;
        if (momentBytes != null) {
          try {
            await widget.client.saveBestMoment(
              widget.token,
              sessionId,
              momentBytes,
              metric: 'shot_motion',
            );
            momentSaved = true;
          } on ApiException catch (e) {
            momentSaveError = e.message;
          } catch (_) {
            momentSaveError = 'The captured frame could not be uploaded.';
          }
        }
      }
    } on ApiException catch (e) {
      saveError = e.message;
    } catch (_) {
      saveError = 'Could not save this session. Check your connection.';
    } finally {
      if (mounted) {
        setState(() => _saving = false);
        widget.onFinish(
          SessionReport(
            durationSeconds: durationSeconds,
            reps: _counter.reps,
            saved: saved,
            leftKnee: metrics?.leftKnee,
            rightKnee: metrics?.rightKnee,
            shoulderTilt: metrics?.shoulderTilt,
            cue: metrics?.cue,
            saveError: saveError,
            bestMomentBytes: momentBytes,
            momentSaved: momentSaved,
            momentSaveError: momentSaveError,
            sessionId: sessionId,
          ),
        );
      }
    }
  }

  InputImageRotation _rotationFromSensor(int sensorDegrees) {
    switch (sensorDegrees) {
      case 90:
        return InputImageRotation.rotation90deg;
      case 180:
        return InputImageRotation.rotation180deg;
      case 270:
        return InputImageRotation.rotation270deg;
      default:
        return InputImageRotation.rotation0deg;
    }
  }

  InputImage? _buildInputImage(CameraImage image, InputImageRotation rotation) {
    if (image.format.group == ImageFormatGroup.nv21 &&
        image.planes.length == 1) {
      final bytes = image.planes.first.bytes;
      final metadata = InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: InputImageFormat.nv21,
        bytesPerRow: image.planes.first.bytesPerRow,
      );
      return InputImage.fromBytes(bytes: bytes, metadata: metadata);
    }
    if (image.format.group == ImageFormatGroup.bgra8888 &&
        image.planes.length == 1) {
      final bytes = image.planes.first.bytes;
      final metadata = InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: InputImageFormat.bgra8888,
        bytesPerRow: image.planes.first.bytesPerRow,
      );
      return InputImage.fromBytes(bytes: bytes, metadata: metadata);
    }
    return null;
  }

  Map<String, PosePoint> _landmarksToMap(
    Map<PoseLandmarkType, PoseLandmark> raw,
  ) {
    PosePoint? get(PoseLandmarkType type) {
      final lm = raw[type];
      if (lm == null) return null;
      return PosePoint(x: lm.x, y: lm.y, confidence: lm.likelihood);
    }

    return {
      'leftShoulder':
          get(PoseLandmarkType.leftShoulder) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'rightShoulder':
          get(PoseLandmarkType.rightShoulder) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'leftElbow':
          get(PoseLandmarkType.leftElbow) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'rightElbow':
          get(PoseLandmarkType.rightElbow) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'leftWrist':
          get(PoseLandmarkType.leftWrist) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'rightWrist':
          get(PoseLandmarkType.rightWrist) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'leftHip':
          get(PoseLandmarkType.leftHip) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'rightHip':
          get(PoseLandmarkType.rightHip) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'leftKnee':
          get(PoseLandmarkType.leftKnee) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'rightKnee':
          get(PoseLandmarkType.rightKnee) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'leftAnkle':
          get(PoseLandmarkType.leftAnkle) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
      'rightAnkle':
          get(PoseLandmarkType.rightAnkle) ??
          const PosePoint(x: 0, y: 0, confidence: 0),
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(backgroundColor: Colors.black, body: _buildBody());
  }

  Widget _buildBody() {
    if (_camError != null) {
      return _ErrorView(
        message: _camError!,
        onBack: widget.onBack,
        onRetry: _restartCamera,
      );
    }
    if (!_camReady) {
      return const SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: CricketColors.mint),
              SizedBox(height: 22),
              Text(
                'OPENING LIVE CAMERA',
                style: TextStyle(
                  color: CricketColors.cream,
                  fontFamily: CricketFonts.display,
                  fontSize: 25,
                ),
              ),
              SizedBox(height: 8),
              Text(
                'Allow camera access to begin pose tracking.',
                style: TextStyle(color: CricketColors.mutedLight, fontSize: 13),
              ),
            ],
          ),
        ),
      );
    }

    final hasBody = _metrics?.hasBody ?? false;
    return Stack(
      fit: StackFit.expand,
      children: [
        _CameraPreviewWidget(
          controller: _cam!,
          overlay: _PoseOverlay(
            landmarks: _landmarks,
            imageSize: _imageSize,
            mirror: _lensDir == CameraLensDirection.front,
          ),
        ),

        // Soft scrims keep the HUD readable over bright frames.
        const IgnorePointer(child: _Scrims()),

        IgnorePointer(
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 350),
            decoration: BoxDecoration(
              border: Border.all(
                color: _momentFlash
                    ? const Color(0xFFF5C542)
                    : Colors.transparent,
                width: 5,
              ),
            ),
          ),
        ),

        IgnorePointer(
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 280),
            child: _paused
                ? const _PausedOverlay(key: ValueKey('paused'))
                : const SizedBox.shrink(),
          ),
        ),

        IgnorePointer(
          child: Align(
            alignment: const Alignment(0, .05),
            child: AnimatedOpacity(
              opacity: _repPulse == null ? 0 : 1,
              duration: const Duration(milliseconds: 260),
              child: AnimatedScale(
                scale: _repPulse == null ? .78 : 1,
                duration: const Duration(milliseconds: 320),
                curve: Curves.easeOutBack,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 14,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xE6063D2A),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: CricketColors.mint, width: 2),
                    boxShadow: const [
                      BoxShadow(
                        color: Colors.black38,
                        blurRadius: 22,
                        offset: Offset(0, 10),
                      ),
                    ],
                  ),
                  child: Text(
                    'REP ${_repPulse ?? _lastReps}',
                    style: CricketFonts.heading(38, color: CricketColors.cream),
                  ),
                ),
              ),
            ),
          ),
        ),

        // HUD: top bar, cue, then controls pinned to the bottom.
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    _GlassIconButton(
                      icon: Icons.close_rounded,
                      tooltip: 'Leave session',
                      onPressed: _saving ? null : _confirmLeave,
                    ),
                    const SizedBox(width: 10),
                    _LivePill(paused: _paused, elapsed: _elapsed),
                    const Spacer(),
                    _HudChip(
                      label: '${_counter.reps}',
                      icon: Icons.repeat_rounded,
                      tooltip: 'Knee bends',
                    ),
                    AnimatedSize(
                      duration: const Duration(milliseconds: 250),
                      curve: kCricketEase,
                      child: _metrics == null
                          ? const SizedBox.shrink()
                          : Padding(
                              padding: const EdgeInsets.only(left: 8),
                              child: _HudChip(
                                label: '${_metrics!.visiblePoints}',
                                icon: Icons.accessibility_new_rounded,
                                tooltip: 'Visible body points',
                              ),
                            ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _CueBanner(
                  cue:
                      _metrics?.cue ??
                      'Stand 2 to 3 metres back, side-on, with your whole body in view.',
                  hasBody: hasBody,
                ),
                const SizedBox(height: 10),
                IgnorePointer(
                  child: AnimatedOpacity(
                    opacity: _momentFlash ? 1 : 0,
                    duration: const Duration(milliseconds: 300),
                    child: AnimatedScale(
                      scale: _momentFlash ? 1 : .92,
                      duration: const Duration(milliseconds: 300),
                      child: const _MomentToast(),
                    ),
                  ),
                ),
                const Spacer(),
                AnimatedSize(
                  duration: const Duration(milliseconds: 280),
                  curve: kCricketEase,
                  child: _metrics == null
                      ? const SizedBox(width: double.infinity)
                      : Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: _AnglePanel(metrics: _metrics!),
                        ),
                ),
                if (_bestMomentPath != null)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.auto_awesome_rounded,
                          color: Color(0xFFF5C542),
                          size: 14,
                        ),
                        SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            'Shot moment captured · saves when you finish',
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: Color(0xFFF5C542),
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                _ControlBar(
                  paused: _paused,
                  saving: _saving,
                  voiceOn: _voiceOn,
                  listening: _voiceListening,
                  onVoiceToggle: () {
                    setState(() => _voiceOn = !_voiceOn);
                    if (_voiceOn) {
                      _speak('Voice coach on.');
                    } else {
                      _tts.stop();
                    }
                  },
                  onListen: _toggleVoiceCommands,
                  onGuide: () => _openShotGuide(null),
                  onPause: _pauseSession,
                  onResume: _resumeSession,
                  onEnd: _endSession,
                ),
                const SizedBox(height: 10),
                Semantics(
                  liveRegion: true,
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 220),
                    child: Text(
                      _commandFeedback,
                      key: ValueKey(_commandFeedback),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: CricketColors.mutedLight,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _confirmLeave() async {
    if (_saving) return;
    final leave = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: CricketColors.night,
        title: Text(
          'LEAVE SESSION?',
          style: CricketFonts.heading(24, color: CricketColors.cream),
        ),
        content: const Text(
          'This session will not be saved. Tap Finish instead to keep it.',
          style: TextStyle(color: CricketColors.mutedLight, height: 1.45),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            style: TextButton.styleFrom(foregroundColor: CricketColors.mint),
            child: const Text('Stay'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.white),
            child: const Text('Leave'),
          ),
        ],
      ),
    );
    if (leave == true && mounted) widget.onBack();
  }
}

// ── Camera preview widget ─────────────────────────────────────────────────────

class _CameraPreviewWidget extends StatelessWidget {
  const _CameraPreviewWidget({required this.controller, this.overlay});
  final CameraController controller;
  final Widget? overlay;

  @override
  Widget build(BuildContext context) {
    // Give CameraPreview finite dimensions. The previous OverflowBox gave
    // its AspectRatio two unbounded axes, which can render an empty preview.
    const previewHeight = 1000.0;
    final previewWidth = previewHeight / controller.value.aspectRatio;
    return ClipRect(
      child: SizedBox.expand(
        child: FittedBox(
          fit: BoxFit.cover,
          alignment: Alignment.center,
          child: SizedBox(
            width: previewWidth,
            height: previewHeight,
            child: CameraPreview(controller, child: overlay),
          ),
        ),
      ),
    );
  }
}

// ── Pose skeleton overlay ─────────────────────────────────────────────────────

class _Joint {
  const _Joint(this.pos, this.conf);
  final Offset pos; // 0 to 1 across the upright preview
  final double conf;
}

/// Shared between the overlay's ticker and its painter so the skeleton
/// repaints at display rate without rebuilding the widget tree.
class _SkeletonFrame extends ChangeNotifier {
  final Map<PoseLandmarkType, _Joint> joints = {};
  double opacity = 0;
  double time = 0;

  void tick() => notifyListeners();
}

/// Draws the tracked body and glides each joint toward the latest detection,
/// so 10 to 15 fps pose results read as smooth 60 fps motion.
class _PoseOverlay extends StatefulWidget {
  const _PoseOverlay({
    required this.landmarks,
    required this.imageSize,
    required this.mirror,
  });
  final List<PoseLandmark> landmarks;
  final Size imageSize;
  final bool mirror;

  @override
  State<_PoseOverlay> createState() => _PoseOverlayState();
}

class _PoseOverlayState extends State<_PoseOverlay>
    with SingleTickerProviderStateMixin {
  final _frame = _SkeletonFrame();
  final Map<PoseLandmarkType, _Joint> _targets = {};
  late final Ticker _ticker;
  Duration _last = Duration.zero;

  @override
  void initState() {
    super.initState();
    _retarget();
    _ticker = createTicker(_tick)..start();
  }

  @override
  void didUpdateWidget(covariant _PoseOverlay old) {
    super.didUpdateWidget(old);
    if (old.landmarks != widget.landmarks ||
        old.imageSize != widget.imageSize) {
      _retarget();
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    _frame.dispose();
    super.dispose();
  }

  void _retarget() {
    _targets.clear();
    final size = widget.imageSize;
    if (size.isEmpty) return;
    for (final lm in widget.landmarks) {
      var x = lm.x / size.width;
      if (widget.mirror) x = 1 - x;
      _targets[lm.type] = _Joint(Offset(x, lm.y / size.height), lm.likelihood);
    }
  }

  void _tick(Duration now) {
    final dt = ((now - _last).inMicroseconds / 1e6).clamp(0.0, .1);
    _last = now;
    final snap = !motionOn(context);
    final joints = _frame.joints;
    if (_targets.isNotEmpty) {
      // Jump straight to the body when it reappears instead of sliding in.
      final k = snap || _frame.opacity < .05 ? 1.0 : 1 - math.exp(-dt * 18);
      joints.removeWhere((type, _) => !_targets.containsKey(type));
      _targets.forEach((type, target) {
        final cur = joints[type];
        joints[type] = cur == null
            ? target
            : _Joint(
                Offset.lerp(cur.pos, target.pos, k)!,
                cur.conf + (target.conf - cur.conf) * k,
              );
      });
    }
    final goal = _targets.isNotEmpty ? 1.0 : 0.0;
    _frame.opacity = snap
        ? goal
        : _frame.opacity + (goal - _frame.opacity) * (1 - math.exp(-dt * 9));
    _frame.time = now.inMicroseconds / 1e6;
    _frame.tick();
  }

  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: _PosePainter(_frame), size: Size.infinite);
}

class _PosePainter extends CustomPainter {
  _PosePainter(this.frame) : super(repaint: frame);
  final _SkeletonFrame frame;

  static const _gold = Color(0xFFF5C542);
  static const _left = CricketColors.mint;
  static const _right = _gold;
  static const _torso = CricketColors.cream;

  static const _bones = <(PoseLandmarkType, PoseLandmarkType, Color)>[
    (PoseLandmarkType.leftShoulder, PoseLandmarkType.rightShoulder, _torso),
    (PoseLandmarkType.leftHip, PoseLandmarkType.rightHip, _torso),
    (PoseLandmarkType.leftShoulder, PoseLandmarkType.leftHip, _torso),
    (PoseLandmarkType.rightShoulder, PoseLandmarkType.rightHip, _torso),
    (PoseLandmarkType.leftShoulder, PoseLandmarkType.leftElbow, _left),
    (PoseLandmarkType.leftElbow, PoseLandmarkType.leftWrist, _left),
    (PoseLandmarkType.leftHip, PoseLandmarkType.leftKnee, _left),
    (PoseLandmarkType.leftKnee, PoseLandmarkType.leftAnkle, _left),
    (PoseLandmarkType.rightShoulder, PoseLandmarkType.rightElbow, _right),
    (PoseLandmarkType.rightElbow, PoseLandmarkType.rightWrist, _right),
    (PoseLandmarkType.rightHip, PoseLandmarkType.rightKnee, _right),
    (PoseLandmarkType.rightKnee, PoseLandmarkType.rightAnkle, _right),
  ];

  static const _bodyJoints = {
    PoseLandmarkType.leftShoulder: _left,
    PoseLandmarkType.rightShoulder: _right,
    PoseLandmarkType.leftElbow: _left,
    PoseLandmarkType.rightElbow: _right,
    PoseLandmarkType.leftWrist: _left,
    PoseLandmarkType.rightWrist: _right,
    PoseLandmarkType.leftHip: _left,
    PoseLandmarkType.rightHip: _right,
    PoseLandmarkType.leftKnee: _left,
    PoseLandmarkType.rightKnee: _right,
    PoseLandmarkType.leftAnkle: _left,
    PoseLandmarkType.rightAnkle: _right,
  };

  static const _keyJoints = {
    PoseLandmarkType.leftKnee,
    PoseLandmarkType.rightKnee,
    PoseLandmarkType.leftElbow,
    PoseLandmarkType.rightElbow,
  };

  /// 0 below 40% likelihood, fully drawn from 75%.
  static double _fade(double conf) => ((conf - .4) / .35).clamp(0.0, 1.0);

  @override
  void paint(Canvas canvas, Size size) {
    final fadeIn = frame.opacity;
    final joints = frame.joints;
    if (fadeIn < .01 || joints.isEmpty) return;
    // The preview box is scaled down by FittedBox, so size strokes to it.
    final s = size.width / 380;
    Offset at(_Joint j) =>
        Offset(j.pos.dx * size.width, j.pos.dy * size.height);

    // Faint torso fill gives the figure body without hiding the batter.
    final torso = [
      joints[PoseLandmarkType.leftShoulder],
      joints[PoseLandmarkType.rightShoulder],
      joints[PoseLandmarkType.rightHip],
      joints[PoseLandmarkType.leftHip],
    ];
    if (torso.every((j) => j != null && j.conf > .5)) {
      final a = fadeIn * torso.map((j) => _fade(j!.conf)).reduce(math.min);
      final path = Path()..addPolygon(torso.map((j) => at(j!)).toList(), true);
      canvas.drawPath(
        path,
        Paint()..color = CricketColors.mint.withValues(alpha: .1 * a),
      );
    }

    for (final (from, to, color) in _bones) {
      final a = joints[from], b = joints[to];
      if (a == null || b == null) continue;
      final alpha = fadeIn * _fade(math.min(a.conf, b.conf));
      if (alpha <= 0) continue;
      final p1 = at(a), p2 = at(b);
      canvas.drawLine(
        p1,
        p2,
        Paint()
          ..color = color.withValues(alpha: .35 * alpha)
          ..strokeWidth = 12 * s
          ..strokeCap = StrokeCap.round
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, 6 * s),
      );
      canvas.drawLine(
        p1,
        p2,
        Paint()
          ..color = color.withValues(alpha: .95 * alpha)
          ..strokeWidth = 4.5 * s
          ..strokeCap = StrokeCap.round,
      );
    }

    _paintHead(canvas, at, s, fadeIn);

    final pulse = (math.sin(frame.time * 5) + 1) / 2;
    joints.forEach((type, joint) {
      final color = _bodyJoints[type];
      if (color == null) return;
      final alpha = fadeIn * _fade(joint.conf);
      if (alpha <= 0) return;
      final p = at(joint);
      final key = _keyJoints.contains(type);
      final r = (key ? 6.5 : 5) * s;
      if (key) {
        canvas.drawCircle(
          p,
          r + (5 + 5 * pulse) * s,
          Paint()
            ..color = color.withValues(alpha: (.28 - .2 * pulse) * alpha)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2 * s,
        );
      }
      canvas.drawCircle(
        p,
        r + 4 * s,
        Paint()
          ..color = color.withValues(alpha: .4 * alpha)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, 5 * s),
      );
      canvas.drawCircle(p, r, Paint()..color = color.withValues(alpha: alpha));
      canvas.drawCircle(
        p,
        r * .45,
        Paint()..color = CricketColors.night.withValues(alpha: alpha),
      );
    });
  }

  void _paintHead(
    Canvas canvas,
    Offset Function(_Joint) at,
    double s,
    double fadeIn,
  ) {
    final joints = frame.joints;
    final nose = joints[PoseLandmarkType.nose];
    final ls = joints[PoseLandmarkType.leftShoulder];
    final rs = joints[PoseLandmarkType.rightShoulder];
    if (nose == null || ls == null || rs == null) return;
    final alpha =
        fadeIn * _fade(math.min(nose.conf, math.min(ls.conf, rs.conf)));
    if (alpha <= 0) return;
    final le = joints[PoseLandmarkType.leftEar];
    final re = joints[PoseLandmarkType.rightEar];
    final shoulders = (at(ls) - at(rs)).distance;
    final earSpan = le != null && re != null ? (at(le) - at(re)).distance : 0;
    final radius = math.max(math.max(earSpan * .75, shoulders * .26), 12 * s);
    final centre = at(nose);
    final neckTop = Offset.lerp(at(ls), at(rs), .5)!;
    final towardNeck = neckTop - centre;
    if (towardNeck.distance > radius) {
      canvas.drawLine(
        centre + towardNeck / towardNeck.distance * radius,
        neckTop,
        Paint()
          ..color = _torso.withValues(alpha: .8 * alpha)
          ..strokeWidth = 3.5 * s
          ..strokeCap = StrokeCap.round,
      );
    }
    canvas.drawCircle(
      centre,
      radius,
      Paint()
        ..color = _torso.withValues(alpha: .3 * alpha)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 10 * s
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 6 * s),
    );
    canvas.drawCircle(
      centre,
      radius,
      Paint()
        ..color = _torso.withValues(alpha: .9 * alpha)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.5 * s,
    );
  }

  @override
  bool shouldRepaint(covariant _PosePainter old) => old.frame != frame;
}

// ── HUD pieces ────────────────────────────────────────────────────────────────

class _Scrims extends StatelessWidget {
  const _Scrims();

  @override
  Widget build(BuildContext context) => const Column(
    children: [
      SizedBox(
        height: 220,
        width: double.infinity,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0x99000000), Color(0x00000000)],
            ),
          ),
        ),
      ),
      Spacer(),
      SizedBox(
        height: 340,
        width: double.infinity,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.bottomCenter,
              end: Alignment.topCenter,
              colors: [Color(0xE6000000), Color(0x8C000000), Color(0x00000000)],
              stops: [0, .5, 1],
            ),
          ),
        ),
      ),
    ],
  );
}

const _glassFill = Color(0x8C0B1A12);
const _glassEdge = Color(0x33FFFFFF);

class _PausedOverlay extends StatelessWidget {
  const _PausedOverlay({super.key});

  @override
  Widget build(BuildContext context) => const ColoredBox(
    color: Color(0x99000000),
    child: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.pause_circle_filled_rounded,
            color: Colors.white,
            size: 72,
          ),
          SizedBox(height: 14),
          Text(
            'SESSION PAUSED',
            style: TextStyle(
              color: Colors.white,
              fontFamily: CricketFonts.display,
              fontSize: 28,
              letterSpacing: .5,
            ),
          ),
          SizedBox(height: 6),
          Text(
            'Tap Resume to continue batting.',
            style: TextStyle(color: CricketColors.mutedLight, fontSize: 14),
          ),
        ],
      ),
    ),
  );
}

/// Repeats [builder]'s 0→1 animation while [active], for pulsing dots and rings.
class _Pulse extends StatefulWidget {
  const _Pulse({required this.active, required this.builder});
  final bool active;
  final Widget Function(BuildContext context, double t) builder;

  @override
  State<_Pulse> createState() => _PulseState();
}

class _PulseState extends State<_Pulse> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sync();
  }

  @override
  void didUpdateWidget(covariant _Pulse old) {
    super.didUpdateWidget(old);
    _sync();
  }

  void _sync() {
    if (widget.active && motionOn(context)) {
      if (!_c.isAnimating) _c.repeat();
    } else {
      _c
        ..stop()
        ..value = 0;
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
    builder: (context, _) => widget.builder(context, _c.value),
  );
}

class _LivePill extends StatelessWidget {
  const _LivePill({required this.paused, required this.elapsed});
  final bool paused;
  final String elapsed;

  @override
  Widget build(BuildContext context) {
    final dot = paused ? Colors.orangeAccent : CricketColors.mint;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: _glassFill,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: paused ? const Color(0x66FFAB40) : _glassEdge,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox.square(
            dimension: 14,
            child: _Pulse(
              active: !paused,
              builder: (context, t) => Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 8 + 6 * t,
                    height: 8 + 6 * t,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: dot.withValues(alpha: .5 * (1 - t)),
                    ),
                  ),
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: dot,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            paused ? 'PAUSED' : 'LIVE',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.4,
            ),
          ),
          Container(
            width: 1,
            height: 14,
            margin: const EdgeInsets.symmetric(horizontal: 10),
            color: Colors.white24,
          ),
          Text(
            elapsed,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w800,
              fontFeatures: [ui.FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

class _HudChip extends StatelessWidget {
  const _HudChip({
    required this.label,
    required this.icon,
    required this.tooltip,
  });
  final String label;
  final IconData icon;
  final String tooltip;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: tooltip,
    child: Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: _glassFill,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: _glassEdge),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: CricketColors.mint, size: 16),
          const SizedBox(width: 6),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 250),
            transitionBuilder: (child, animation) => ScaleTransition(
              scale: animation,
              child: FadeTransition(opacity: animation, child: child),
            ),
            child: Text(
              label,
              key: ValueKey(label),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.w800,
                fontFeatures: [ui.FontFeature.tabularFigures()],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _GlassIconButton extends StatelessWidget {
  const _GlassIconButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.active = false,
    this.size = 40,
  });
  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;
  final bool active;
  final double size;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: tooltip,
    child: SizedBox.square(
      dimension: size,
      child: _Pulse(
        active: active,
        builder: (context, t) => Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            if (active)
              Container(
                width: size + 16 * t,
                height: size + 16 * t,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: CricketColors.mint.withValues(alpha: 1 - t),
                    width: 2,
                  ),
                ),
              ),
            AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: active ? CricketColors.mint : _glassFill,
                border: Border.all(
                  color: active ? CricketColors.mint : _glassEdge,
                ),
              ),
              child: Material(
                type: MaterialType.transparency,
                shape: const CircleBorder(),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: onPressed,
                  child: SizedBox.square(
                    dimension: size,
                    child: Icon(
                      icon,
                      size: size * .48,
                      color: onPressed == null
                          ? Colors.white38
                          : active
                          ? CricketColors.night
                          : CricketColors.cream,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _MomentToast extends StatelessWidget {
  const _MomentToast();

  @override
  Widget build(BuildContext context) => Center(
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
      decoration: BoxDecoration(
        color: const Color(0xEE063D2A),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: const Color(0xFFF5C542), width: 1.5),
        boxShadow: const [
          BoxShadow(
            color: Colors.black38,
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.auto_awesome_rounded, color: Color(0xFFF5C542), size: 19),
          SizedBox(width: 8),
          Text(
            'BEST MOMENT CAPTURED',
            style: TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
            ),
          ),
        ],
      ),
    ),
  );
}

// ── Cue banner ────────────────────────────────────────────────────────────────

class _CueBanner extends StatelessWidget {
  const _CueBanner({required this.cue, required this.hasBody});
  final String cue;
  final bool hasBody;

  @override
  Widget build(BuildContext context) {
    final accent = hasBody ? CricketColors.mint : const Color(0xFFFFB74D);
    return AnimatedContainer(
      duration: const Duration(milliseconds: 320),
      curve: kCricketEase,
      padding: const EdgeInsets.fromLTRB(12, 12, 16, 12),
      decoration: BoxDecoration(
        color: hasBody ? const Color(0xB3062A1B) : const Color(0xCC5E0A1A),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: accent.withValues(alpha: .55)),
        boxShadow: const [
          BoxShadow(
            color: Colors.black26,
            blurRadius: 16,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 320),
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: accent.withValues(alpha: .18),
            ),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 250),
              transitionBuilder: (child, animation) =>
                  ScaleTransition(scale: animation, child: child),
              child: Icon(
                hasBody ? Icons.check_rounded : Icons.accessibility_new_rounded,
                key: ValueKey(hasBody),
                color: accent,
                size: 18,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 260),
              layoutBuilder: (current, previous) => Stack(
                alignment: Alignment.centerLeft,
                children: [...previous, ?current],
              ),
              transitionBuilder: (child, animation) => FadeTransition(
                opacity: animation,
                child: SlideTransition(
                  position: Tween(
                    begin: const Offset(0, .25),
                    end: Offset.zero,
                  ).animate(animation),
                  child: child,
                ),
              ),
              child: Text(
                cue,
                key: ValueKey(cue),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  height: 1.35,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Angle panel ───────────────────────────────────────────────────────────────

class _AnglePanel extends StatelessWidget {
  const _AnglePanel({required this.metrics});
  final PoseMetrics metrics;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: _AngleTile(label: 'L KNEE', value: metrics.leftKnee),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _AngleTile(label: 'R KNEE', value: metrics.rightKnee),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _AngleTile(label: 'L ELBOW', value: metrics.leftElbow),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _AngleTile(label: 'R ELBOW', value: metrics.rightElbow),
      ),
    ],
  );
}

class _AngleTile extends StatelessWidget {
  const _AngleTile({required this.label, required this.value});
  final String label;
  final double? value;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(vertical: 8),
    decoration: BoxDecoration(
      color: _glassFill,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _glassEdge),
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          maxLines: 1,
          style: const TextStyle(
            color: Color(0xFF9BDFB7),
            fontSize: 9.5,
            fontWeight: FontWeight.w700,
            letterSpacing: .8,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          value != null ? '${value!.round()}°' : '--',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 17,
            fontWeight: FontWeight.w800,
            fontFeatures: [ui.FontFeature.tabularFigures()],
          ),
        ),
      ],
    ),
  );
}

// ── Control bar ───────────────────────────────────────────────────────────────

class _ControlBar extends StatelessWidget {
  const _ControlBar({
    required this.paused,
    required this.saving,
    required this.voiceOn,
    required this.listening,
    required this.onVoiceToggle,
    required this.onListen,
    required this.onGuide,
    required this.onPause,
    required this.onResume,
    required this.onEnd,
  });
  final bool paused;
  final bool saving;
  final bool voiceOn;
  final bool listening;
  final VoidCallback onVoiceToggle;
  final VoidCallback onListen;
  final VoidCallback onGuide;
  final VoidCallback onPause;
  final VoidCallback onResume;
  final VoidCallback onEnd;

  static const _labelStyle = TextStyle(
    fontFamily: CricketFonts.body,
    fontSize: 15,
    fontWeight: FontWeight.w800,
  );

  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      // Secondary tools sit above the two primary actions.
      Row(
        children: [
          _GlassIconButton(
            icon: voiceOn ? Icons.volume_up_rounded : Icons.volume_off_rounded,
            tooltip: voiceOn ? 'Mute voice coach' : 'Enable voice coach',
            onPressed: saving ? null : onVoiceToggle,
            size: 48,
          ),
          const SizedBox(width: 10),
          _GlassIconButton(
            key: const Key('live-mic'),
            icon: listening ? Icons.mic_rounded : Icons.mic_none_rounded,
            tooltip: listening ? 'Stop listening' : 'Voice commands',
            onPressed: saving ? null : onListen,
            active: listening,
            size: 48,
          ),
          const Spacer(),
          SizedBox(
            height: 48,
            child: OutlinedButton.icon(
              onPressed: saving ? null : onGuide,
              style: OutlinedButton.styleFrom(
                foregroundColor: CricketColors.cream,
                backgroundColor: _glassFill,
                side: const BorderSide(color: _glassEdge),
                minimumSize: const Size(0, 48),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                textStyle: _labelStyle.copyWith(fontSize: 13.5),
              ),
              icon: const Icon(Icons.sports_cricket_rounded, size: 18),
              label: const Text('Learn a shot'),
            ),
          ),
        ],
      ),
      const SizedBox(height: 12),
      Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              key: const Key('live-pause'),
              onPressed: saving
                  ? null
                  : paused
                  ? onResume
                  : onPause,
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                backgroundColor: paused
                    ? const Color(0xCC0F5C3A)
                    : const Color(0x99000000),
                side: BorderSide(
                  color: paused ? CricketColors.mint : Colors.white38,
                  width: 1.5,
                ),
                minimumSize: const Size.fromHeight(56),
                padding: const EdgeInsets.symmetric(horizontal: 12),
                textStyle: _labelStyle,
              ),
              icon: AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                transitionBuilder: (child, animation) =>
                    RotationTransition(turns: animation, child: child),
                child: Icon(
                  paused ? Icons.play_arrow_rounded : Icons.pause_rounded,
                  key: ValueKey(paused),
                  size: 22,
                ),
              ),
              label: Text(
                paused ? 'Resume' : 'Pause',
                maxLines: 1,
                softWrap: false,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: FilledButton.icon(
              key: const Key('live-finish'),
              onPressed: saving ? null : onEnd,
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(56),
                padding: const EdgeInsets.symmetric(horizontal: 12),
                textStyle: _labelStyle,
                disabledBackgroundColor: const Color(0x99C8102E),
                disabledForegroundColor: Colors.white70,
              ),
              icon: saving
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.stop_rounded, size: 22),
              label: Text(
                saving ? 'Saving…' : 'Finish',
                maxLines: 1,
                softWrap: false,
              ),
            ),
          ),
        ],
      ),
    ],
  );
}

// ── Error view ────────────────────────────────────────────────────────────────

class _ErrorView extends StatelessWidget {
  const _ErrorView({
    required this.message,
    required this.onBack,
    required this.onRetry,
  });
  final String message;
  final VoidCallback onBack;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.videocam_off_rounded,
            color: Colors.white54,
            size: 64,
          ),
          const SizedBox(height: 20),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 16,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Retry camera'),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: onBack,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              side: const BorderSide(color: Colors.white54),
            ),
            icon: const Icon(Icons.arrow_back_rounded),
            label: const Text('Back to check-in'),
          ),
        ],
      ),
    ),
  );
}
