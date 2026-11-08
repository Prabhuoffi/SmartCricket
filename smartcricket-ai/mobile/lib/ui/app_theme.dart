import 'package:flutter/material.dart';

/// The website's brand (frontend/css/landing.css): turf green, players'-whites cream, cricket-ball red.
abstract final class CricketColors {
  static const green = Color(0xFF0F5C3A); // --primary
  static const night = Color(0xFF062A1B); // --night
  static const night2 = Color(0xFF0A3D27); // --night-2
  static const deepGreen = night;
  static const pitch = Color(0xFF1F9D55);
  static const secondary = Color(0xFFF3E9D2); // cream accents on dark
  static const cream = Color(0xFFFBF7EE); // --paper, page background
  static const light = Color(0xFFFFFDF8); // --light, text on dark
  static const red = Color(0xFFC8102E); // --tertiary
  static const mint = Color(0xFF7FD1A0);
  static const ink = Color(0xFF0B1A12);
  static const muted = Color(0xA30B1A12); // rgba(11, 26, 18, .64)
  static const mutedLight = Color(0xB8FFFDF8); // rgba(255, 253, 248, .72)
  static const line = Color(0x1A0B1A12); // rgba(11, 26, 18, .1)
}

abstract final class CricketFonts {
  static const body = 'PlusJakartaSans';
  static const display = 'Anton';

  /// Big uppercase headings, like the website's h1 and h2.
  static TextStyle heading(double size, {Color color = CricketColors.ink, double height = 1}) => TextStyle(
    fontFamily: display,
    fontSize: size,
    height: height,
    letterSpacing: size * .01,
    color: color,
  );

  /// Small uppercase label with the red dash in front (the website's .eyebrow), as text style only.
  static const eyebrow = TextStyle(
    fontFamily: body,
    fontSize: 11.5,
    fontWeight: FontWeight.w800,
    letterSpacing: 2.1,
  );
}

/// The website's easing curve, cubic-bezier(.22, 1, .36, 1).
const kCricketEase = Cubic(.22, 1, .36, 1);

abstract final class SmartCricketTheme {
  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: CricketColors.green,
      primary: CricketColors.green,
      secondary: CricketColors.red,
      surface: CricketColors.cream,
      error: const Color(0xFFAD1930),
    );
    final base = ThemeData(useMaterial3: true, colorScheme: scheme, fontFamily: CricketFonts.body);
    final pill = RoundedRectangleBorder(borderRadius: BorderRadius.circular(999));
    return base.copyWith(
      scaffoldBackgroundColor: CricketColors.cream,
      textTheme: base.textTheme.apply(
        fontFamily: CricketFonts.body,
        bodyColor: CricketColors.ink,
        displayColor: CricketColors.ink,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: CricketColors.cream,
        foregroundColor: CricketColors.ink,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: CricketColors.red,
          foregroundColor: Colors.white,
          minimumSize: const Size(48, 54),
          padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 15),
          shape: pill,
          elevation: 0,
          shadowColor: CricketColors.red,
          textStyle: const TextStyle(fontFamily: CricketFonts.body, fontSize: 16, fontWeight: FontWeight.w800, letterSpacing: .2),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 52),
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
          shape: pill,
          side: const BorderSide(color: CricketColors.line, width: 2),
          textStyle: const TextStyle(fontFamily: CricketFonts.body, fontSize: 15, fontWeight: FontWeight.w800),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: CricketColors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: CricketColors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: CricketColors.green, width: 2),
        ),
      ),
      dividerTheme: const DividerThemeData(color: CricketColors.line),
    );
  }
}
