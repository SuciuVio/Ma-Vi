import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api/mavi_api.dart';
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
  final _api = MaviApi();
  String? _token;
  bool _loadingSession = true;

  @override
  void initState() {
    super.initState();
    _loadSavedSession();
  }

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
          ? _loadingSession
              ? const _LoadingSessionScreen()
              : LoginScreen(onSignedIn: _saveSession)
          : ChatListScreen(token: _token!, onLogout: _logout),
    );
  }

  Future<void> _loadSavedSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('mavi_token');
    final refreshToken = prefs.getString('mavi_refresh_token');
    if (refreshToken != null && refreshToken.isNotEmpty) {
      try {
        final session = await _api.refresh(refreshToken);
        await _saveSession(session);
        return;
      } catch (_) {
        await prefs.remove('mavi_token');
        await prefs.remove('mavi_refresh_token');
        await prefs.remove('mavi_username');
      }
    }
    if (!mounted) return;
    setState(() {
      _token = token;
      _loadingSession = false;
    });
  }

  Future<void> _saveSession(AuthSession session) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('mavi_token', session.token);
    await prefs.setString('mavi_refresh_token', session.refreshToken);
    await prefs.setString('mavi_username', session.username);
    if (!mounted) return;
    setState(() {
      _token = session.token;
      _loadingSession = false;
    });
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('mavi_token');
    await prefs.remove('mavi_refresh_token');
    await prefs.remove('mavi_username');
    if (!mounted) return;
    setState(() {
      _token = null;
      _loadingSession = false;
    });
  }
}

class _LoadingSessionScreen extends StatelessWidget {
  const _LoadingSessionScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
