import 'package:flutter/material.dart';

import 'screens/chat_list_screen.dart';
import 'screens/login_screen.dart';

void main() {
  runApp(const MaviApp());
}

class MaviApp extends StatefulWidget {
  const MaviApp({super.key});

  @override
  State<MaviApp> createState() => _MaviAppState();
}

class _MaviAppState extends State<MaviApp> {
  String? _token;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Ma:Vi',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF128C7E),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF0B141A),
        useMaterial3: true,
      ),
      home: _token == null
          ? LoginScreen(onSignedIn: (token) => setState(() => _token = token))
          : ChatListScreen(token: _token!, onLogout: () => setState(() => _token = null)),
    );
  }
}
