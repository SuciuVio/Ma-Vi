import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:open_filex/open_filex.dart';

import '../api/mavi_api.dart';
import '../models.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.token, required this.peer});

  final String token;
  final MaviUser peer;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _api = MaviApi();
  final _message = TextEditingController();
  List<MaviMessage> _messages = [];
  String _status = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.peer.username)),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (context, index) => _MessageBubble(
                message: _messages[index],
                attachmentUrl: _messages[index].attachmentId == null ? null : _api.attachmentUrl(_messages[index].attachmentId!),
                token: widget.token,
                mine: _messages[index].senderId != widget.peer.id,
                onDownload: () => _download(_messages[index]),
              ),
            ),
          ),
          if (_status.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: Text(_status)),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
              child: Row(
                children: [
                  IconButton(onPressed: _attach, icon: const Icon(Icons.attach_file)),
                  Expanded(
                    child: TextField(
                      controller: _message,
                      decoration: const InputDecoration(hintText: 'Message', filled: true),
                      minLines: 1,
                      maxLines: 4,
                    ),
                  ),
                  IconButton.filled(onPressed: _send, icon: const Icon(Icons.send)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _load() async {
    final messages = await _api.messages(widget.token, widget.peer.id);
    setState(() => _messages = messages);
  }

  Future<void> _send() async {
    final text = _message.text.trim();
    if (text.isEmpty) return;
    _message.clear();
    final sent = await _api.sendMessage(widget.token, widget.peer.id, text);
    setState(() => _messages = [..._messages, sent]);
  }

  Future<void> _attach() async {
    final selected = await FilePicker.platform.pickFiles(type: FileType.any);
    final path = selected?.files.single.path;
    if (path == null) return;
    setState(() => _status = 'Uploading...');
    try {
      final attachmentId = await _api.uploadAttachment(widget.token, File(path));
      final name = selected!.files.single.name;
      final type = _isImageName(name) ? 'image' : 'file';
      final sent = await _api.sendMessage(widget.token, widget.peer.id, name, attachmentId: attachmentId, type: type);
      setState(() {
        _messages = [..._messages, sent];
        _status = '';
      });
    } catch (error) {
      setState(() => _status = 'Upload failed: $error');
    }
  }

  Future<void> _download(MaviMessage message) async {
    setState(() => _status = 'Downloading...');
    try {
      final file = await _api.downloadAttachment(widget.token, message);
      setState(() => _status = 'Downloaded: ${file.path.split(Platform.pathSeparator).last}');
      await OpenFilex.open(file.path);
    } catch (error) {
      setState(() => _status = 'Download failed: $error');
    }
  }

  bool _isImageName(String name) {
    final lower = name.toLowerCase();
    return lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png') || lower.endsWith('.gif') || lower.endsWith('.webp') || lower.endsWith('.bmp');
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message, required this.attachmentUrl, required this.token, required this.mine, required this.onDownload});

  final MaviMessage message;
  final String? attachmentUrl;
  final String token;
  final bool mine;
  final VoidCallback onDownload;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: mine ? const Color(0xFF005C4B) : const Color(0xFF202C33),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (attachmentUrl != null && message.isImage) ...[
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 220, minWidth: 180),
                      child: Image.network(attachmentUrl!, headers: {'Authorization': 'Bearer $token'}, fit: BoxFit.cover),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                if (attachmentUrl != null && !message.isImage)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.insert_drive_file, size: 20),
                      const SizedBox(width: 8),
                      Flexible(child: Text(message.fileName ?? message.content, overflow: TextOverflow.ellipsis)),
                    ],
                  ),
                if (attachmentUrl == null || !message.isImage)
                  Text(message.content, style: const TextStyle(fontSize: 16)),
                if (attachmentUrl != null)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(onPressed: onDownload, icon: const Icon(Icons.download, size: 18), label: const Text('Download')),
                  ),
                const SizedBox(height: 4),
                Text(message.timestamp, style: TextStyle(color: Colors.white.withValues(alpha: 0.55), fontSize: 11)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
