import 'package:flutter/material.dart';

import '../api/mavi_api.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.onSignedIn});

  final ValueChanged<String> onSignedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _api = MaviApi();
  final _username = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _register = false;
  String _status = '';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const SizedBox(height: 48),
            const Text('Ma:Vi', style: TextStyle(fontSize: 42, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(_register ? 'Create your encrypted chat account' : 'Sign in to continue'),
            const SizedBox(height: 32),
            TextField(controller: _username, decoration: const InputDecoration(labelText: 'Username')),
            if (_register) TextField(controller: _email, decoration: const InputDecoration(labelText: 'Email')),
            TextField(controller: _password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
            const SizedBox(height: 24),
            FilledButton(onPressed: _submit, child: Text(_register ? 'Create account' : 'Sign in')),
            TextButton(onPressed: () => setState(() => _register = !_register), child: Text(_register ? 'I already have an account' : 'Create account')),
            if (_status.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 16), child: Text(_status)),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    setState(() => _status = 'Connecting...');
    try {
      final token = _register
          ? await _api.register(_username.text.trim(), _email.text.trim(), _password.text)
          : await _api.login(_username.text.trim(), _password.text);
      widget.onSignedIn(token);
    } catch (error) {
      setState(() => _status = 'Failed: $error');
    }
  }
}
