import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:snapsort/main.dart';

void main() {
  testWidgets('shows branded onboarding after splash', (tester) async {
    await tester.pumpWidget(const SnapSortApp());
    await tester.pump(const Duration(milliseconds: 900));
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Every moment, easy to find.'), findsOneWidget);
    expect(find.text('Get started'), findsNothing);
  });

  testWidgets('login validates required fields', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));
    await tester.tap(find.text('Sign in'));
    await tester.pump();

    expect(find.text('Enter a valid email address'), findsOneWidget);
    expect(find.text('Use at least 6 characters'), findsOneWidget);
  });
}
