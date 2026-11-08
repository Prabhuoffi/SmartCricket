import 'dart:convert';

import 'package:flutter/services.dart';

class ShotGuide {
  const ShotGuide({
    required this.name,
    required this.aliases,
    required this.family,
    required this.when,
    required this.steps,
    required this.cue,
  });

  final String name;
  final List<String> aliases;
  final String family;
  final String when;
  final List<String> steps;
  final String cue;

  factory ShotGuide.fromJson(Map<String, dynamic> json) => ShotGuide(
    name: json['name'] as String,
    aliases: (json['aliases'] as List).cast<String>(),
    family: json['family'] as String,
    when: json['when'] as String,
    steps: (json['steps'] as List).cast<String>(),
    cue: json['cue'] as String,
  );

  String get spokenGuide => '$name. $when ${steps.join(' ')} $cue';
}

class ShotGuides {
  static Future<List<ShotGuide>> load() async {
    final raw = await rootBundle.loadString('assets/shot-guides.json');
    return (jsonDecode(raw) as List)
        .map((entry) => ShotGuide.fromJson(entry as Map<String, dynamic>))
        .toList();
  }

  static ShotGuide? match(String text, List<ShotGuide> guides) {
    final said = text.toLowerCase();
    final aliases = [
      for (final guide in guides)
        for (final alias in guide.aliases)
          (alias: alias.toLowerCase(), guide: guide),
    ]..sort((a, b) => b.alias.length.compareTo(a.alias.length));
    for (final entry in aliases) {
      final pattern = RegExp(
        '(^|[^a-z])${RegExp.escape(entry.alias)}(?=\$|[^a-z])',
      );
      if (pattern.hasMatch(said)) return entry.guide;
    }
    return null;
  }
}
