import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../data/api_client.dart';
import '../ui/app_theme.dart';
import '../ui/brand.dart';

class LiveHistoryScreen extends StatefulWidget {
  const LiveHistoryScreen({
    super.key,
    required this.client,
    required this.token,
    required this.onBack,
    required this.onLogout,
  });

  final ApiClient client;
  final String token;
  final ValueChanged<bool> onBack;
  final VoidCallback onLogout;

  @override
  State<LiveHistoryScreen> createState() => _LiveHistoryScreenState();
}

class _LiveHistoryScreenState extends State<LiveHistoryScreen> {
  late Future<List<LiveSessionEntry>> _history;
  final Map<int, Future<Uint8List>> _images = {};
  int? _deleting;
  bool _changed = false;

  @override
  void initState() {
    super.initState();
    _history = widget.client.liveHistory(widget.token);
  }

  void _reload() {
    _images.clear();
    setState(() {
      _history = widget.client.liveHistory(widget.token);
    });
  }

  Future<void> _delete(
    LiveSessionEntry session, {
    required bool imageOnly,
  }) async {
    if (_deleting != null) return;
    final approved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          imageOnly ? 'Delete captured image?' : 'Delete live session?',
        ),
        content: Text(
          imageOnly
              ? 'The session and its measurements will stay in History.'
              : 'The session, its image and its live-session XP will be removed.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(imageOnly ? 'Delete image' : 'Delete session'),
          ),
        ],
      ),
    );
    if (approved != true || !mounted) return;
    setState(() => _deleting = session.id);
    try {
      if (imageOnly) {
        await widget.client.deleteLiveMoment(widget.token, session.id);
      } else {
        await widget.client.deleteLiveSession(widget.token, session.id);
      }
      if (!mounted) return;
      _changed = true;
      _reload();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            imageOnly ? 'Captured image deleted.' : 'Live session deleted.',
          ),
        ),
      );
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _deleting = null);
    }
  }

  String _date(DateTime date) {
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    final local = date.toLocal();
    return '${local.day} ${months[local.month - 1]} ${local.year}';
  }

  Widget _image(LiveSessionEntry session) {
    if (!session.hasImage) {
      return const SizedBox(
        height: 176,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.videocam_outlined,
                size: 42,
                color: CricketColors.muted,
              ),
              SizedBox(height: 8),
              Text(
                'No shot image captured',
                style: TextStyle(color: CricketColors.muted),
              ),
            ],
          ),
        ),
      );
    }
    final image = _images.putIfAbsent(
      session.id,
      () => widget.client.liveMoment(widget.token, session.id),
    );
    return FutureBuilder<Uint8List>(
      future: image,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return const SizedBox(
            height: 176,
            child: Center(child: Text('Image unavailable')),
          );
        }
        if (!snapshot.hasData) {
          return const SizedBox(
            height: 176,
            child: Center(child: CircularProgressIndicator()),
          );
        }
        final bytes = snapshot.data!;
        return InkWell(
          onTap: () => showDialog<void>(
            context: context,
            builder: (context) => Dialog(
              child: Stack(
                children: [
                  InteractiveViewer(
                    child: Image.memory(bytes, fit: BoxFit.contain),
                  ),
                  Positioned(
                    top: 4,
                    right: 4,
                    child: IconButton.filledTonal(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ),
                ],
              ),
            ),
          ),
          child: SizedBox(
            height: 190,
            width: double.infinity,
            child: Image.memory(bytes, fit: BoxFit.cover),
          ),
        );
      },
    );
  }

  Widget _card(LiveSessionEntry session) => Card(
    clipBehavior: Clip.antiAlias,
    margin: const EdgeInsets.only(bottom: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _image(session),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                session.title,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                '${_date(session.createdAt)} · ${session.durationSeconds ~/ 60}m ${session.durationSeconds % 60}s'
                '${session.reps > 0 ? ' · ${session.reps} reps' : ''}',
                style: const TextStyle(
                  color: CricketColors.muted,
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  if (session.hasImage)
                    OutlinedButton.icon(
                      onPressed: _deleting == null
                          ? () => _delete(session, imageOnly: true)
                          : null,
                      icon: const Icon(
                        Icons.image_not_supported_outlined,
                        size: 17,
                      ),
                      label: const Text('Delete image'),
                    ),
                  TextButton.icon(
                    onPressed: _deleting == null
                        ? () => _delete(session, imageOnly: false)
                        : null,
                    icon: const Icon(Icons.delete_outline_rounded, size: 17),
                    label: const Text('Delete session'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const CricketBrand(compact: true),
      leading: IconButton(
        onPressed: () => widget.onBack(_changed),
        icon: const Icon(Icons.arrow_back_rounded),
        tooltip: 'Back',
      ),
      actions: [
        IconButton(
          onPressed: _reload,
          icon: const Icon(Icons.refresh_rounded),
          tooltip: 'Refresh history',
        ),
        TextButton(onPressed: widget.onLogout, child: const Text('Sign out')),
      ],
    ),
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: FutureBuilder<List<LiveSessionEntry>>(
            future: _history,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('Could not load live history.'),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: _reload,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                );
              }
              if (!snapshot.hasData) {
                return const Center(child: CircularProgressIndicator());
              }
              final sessions = snapshot.data!;
              return ListView(
                padding: const EdgeInsets.fromLTRB(18, 16, 18, 28),
                children: [
                  Text(
                    'LIVE HISTORY',
                    style: CricketFonts.heading(30, color: CricketColors.night),
                  ),
                  const SizedBox(height: 5),
                  const Text(
                    'Your saved live practice and shot images.',
                    style: TextStyle(color: CricketColors.muted),
                  ),
                  const SizedBox(height: 18),
                  if (sessions.isEmpty)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 70),
                      child: Center(child: Text('No live sessions saved yet.')),
                    )
                  else
                    ...sessions.map(_card),
                ],
              );
            },
          ),
        ),
      ),
    ),
  );
}
