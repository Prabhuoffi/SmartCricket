import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartcricket_ai/training/shot_guide.dart';
import 'package:smartcricket_ai/training/shot_guide_sheet.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('front foot and hook speech resolve to the correct guide', () async {
    final guides = await ShotGuides.load();
    expect(
      ShotGuides.match('How do I play a front foot shot?', guides)?.name,
      'Front foot drive',
    );
    expect(
      ShotGuides.match('Show me the hook shot', guides)?.name,
      'Hook shot',
    );
    expect(ShotGuides.match('stop the camera', guides), isNull);
    expect(guides.every((guide) => guide.steps.length == 3), isTrue);
  });

  testWidgets('a narrow phone shows and advances the illustrated shot steps', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final guides = await tester.runAsync(ShotGuides.load) ?? [];
    final hook = ShotGuides.match('hook shot', guides)!;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ShotGuideSheet(
            guides: guides,
            initial: hook,
            onNarrate: (_) {},
          ),
        ),
      ),
    );
    expect(find.text('Hook shot'), findsOneWidget);
    expect(find.textContaining('SET UP'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 1900));
    expect(find.textContaining('MOVE'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
