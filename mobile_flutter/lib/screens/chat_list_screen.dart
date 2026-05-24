import 'package:flutter/material.dart';

import '../api/mavi_api.dart';
import '../models.dart';
import 'chat_screen.dart';

class ChatListScreen extends StatefulWidget {
  const ChatListScreen({super.key, required this.token, required this.onLogout});

  final String token;
  final VoidCallback onLogout;

  @override
  State<ChatListScreen> createState() => _ChatListScreenState();
}

class _ChatListScreenState extends State<ChatListScreen> {
  final _api = MaviApi();
  final _query = TextEditingController();
  List<MaviUser> _users = [];
  String _status = '';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ma:Vi'),
        actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: SearchBar(
              controller: _query,
              hintText: 'Search people',
              leading: const Icon(Icons.search),
              onSubmitted: (_) => _search(),
              trailing: [IconButton(onPressed: _search, icon: const Icon(Icons.arrow_forward))],
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: _users.length,
              itemBuilder: (context, index) {
                final user = _users[index];
                return ListTile(
                  leading: CircleAvatar(child: Text(user.username.characters.first.toUpperCase())),
                  title: Text(user.username),
                  subtitle: Text(user.status),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => ChatScreen(token: widget.token, peer: user))),
                );
              },
            ),
          ),
          if (_status.isNotEmpty) Padding(padding: const EdgeInsets.all(12), child: Text(_status)),
        ],
      ),
    );
  }

  Future<void> _search() async {
    setState(() => _status = 'Searching...');
    try {
      final users = await _api.search(widget.token, _query.text.trim());
      setState(() {
        _users = users;
        _status = users.isEmpty ? 'No users found' : '';
      });
    } catch (error) {
      setState(() => _status = 'Search failed: $error');
    }
  }
}
