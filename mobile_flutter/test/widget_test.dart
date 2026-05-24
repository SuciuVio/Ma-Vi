import 'package:flutter_test/flutter_test.dart';
import 'package:mavi_mobile/main.dart';

void main() {
  testWidgets('Ma:Vi app starts on login screen', (tester) async {
    await tester.pumpWidget(const MaviApp());

    expect(find.text('Ma:Vi'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
