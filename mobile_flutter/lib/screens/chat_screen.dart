import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:open_filex/open_filex.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

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
  WebSocketChannel? _socket;
  RTCPeerConnection? _peerConnection;
  MediaStream? _localStream;
  MediaStream? _remoteStream;
  List<MaviMessage> _messages = [];
  String _status = '';
  int? _callId;
  int? _pendingAnswerCallId;
  bool _callMuted = false;
  String _callStatus = '';

  @override
  void initState() {
    super.initState();
    _load();
    _connectRealtime();
  }

  @override
  void dispose() {
    _socket?.sink.close();
    _disposeWebRtc();
    _message.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.peer.username),
        actions: [
          IconButton(
            tooltip: 'Audio call',
            onPressed: _callId == null ? _startCall : null,
            icon: const Icon(Icons.call),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_callId != null) _CallBanner(status: _callStatus, muted: _callMuted, onEnd: _endCall, onMute: _toggleMute),
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

  void _connectRealtime() {
    final uri = _api.wsUri('/ws/chat', {'token': widget.token});
    final socket = WebSocketChannel.connect(uri);
    _socket = socket;
    socket.stream.listen((payload) {
      if (!mounted) return;
      final data = jsonDecode(payload as String) as Map<String, dynamic>;
      final event = data['event'] as String? ?? '';
      if (event == 'message') {
        final message = MaviMessage.fromJson(data['message'] as Map<String, dynamic>);
        if (message.senderId == widget.peer.id || message.receiverId == widget.peer.id) {
          setState(() => _messages = [..._messages, message]);
        }
      } else if (event == 'call_started') {
        final call = data['call'] as Map<String, dynamic>;
        if (call['caller_id'] == widget.peer.id) {
          _showIncomingCall(call);
        }
      } else if (event == 'call_answered') {
        setState(() {
          _callStatus = 'Audio call active';
        });
      } else if (event == 'call_rejected' || event == 'call_ended') {
        _clearCall(event == 'call_rejected' ? 'Call rejected' : 'Call ended');
      } else if (event == 'call_muted') {
        setState(() => _callStatus = 'Call updated');
      } else if (event == 'webrtc_offer') {
        _handleWebRtcOffer(data);
      } else if (event == 'webrtc_answer') {
        _handleWebRtcAnswer(data);
      } else if (event == 'webrtc_ice') {
        _handleWebRtcIce(data);
      }
    }, onError: (_) {
      if (mounted) setState(() => _status = 'Realtime disconnected');
    });
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

  Future<void> _startCall() async {
    setState(() => _callStatus = 'Calling ${widget.peer.username}...');
    try {
      final call = await _api.startCall(widget.token, widget.peer.id);
      setState(() {
        _callId = call['id'] as int;
        _callStatus = 'Ringing...';
      });
      await _startWebRtcOffer(int.parse('${call['id']}'));
    } catch (error) {
      setState(() => _status = 'Call failed: $error');
    }
  }

  Future<void> _answerCall() async {
    final callId = _callId;
    if (callId == null) return;
    await _api.respondCall(widget.token, callId, true);
    await _acceptWebRtcCall(callId);
    if (!mounted) return;
    setState(() {
      _callStatus = 'Audio call active';
    });
  }

  Future<void> _rejectCall() async {
    final callId = _callId;
    if (callId == null) return;
    await _api.respondCall(widget.token, callId, false);
    if (!mounted) return;
    _clearCall('Call rejected');
  }

  Future<void> _endCall() async {
    final callId = _callId;
    if (callId == null) return;
    await _api.endCall(widget.token, callId);
    await _disposeWebRtc();
    if (!mounted) return;
    _clearCall('Call ended');
  }

  Future<void> _toggleMute() async {
    final callId = _callId;
    if (callId == null) return;
    final muted = !_callMuted;
    await _api.muteCall(widget.token, callId, muted);
    _setLocalMute(muted);
    if (!mounted) return;
    setState(() {
      _callMuted = muted;
      _callStatus = muted ? 'Muted' : 'Audio call active';
    });
  }

  void _showIncomingCall(Map<String, dynamic> call) {
    setState(() {
      _callId = call['id'] as int;
      _callStatus = 'Incoming audio call';
    });
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Text('${widget.peer.username} is calling'),
        content: const Text('Incoming audio call'),
        actions: [
          TextButton(onPressed: () { Navigator.of(context).pop(); _rejectCall(); }, child: const Text('Decline')),
          FilledButton(onPressed: () { Navigator.of(context).pop(); _answerCall(); }, child: const Text('Answer')),
        ],
      ),
    );
  }

  void _clearCall(String status) {
    setState(() {
      _callId = null;
      _callMuted = false;
      _callStatus = '';
      _status = status;
    });
    _disposeWebRtc();
  }

  Future<RTCPeerConnection> _ensurePeerConnection() async {
    if (_peerConnection != null) return _peerConnection!;
    final config = {
      'iceServers': [
        {'urls': 'stun:stun.l.google.com:19302'},
        {'urls': 'stun:stun1.l.google.com:19302'},
      ],
    };
    final pc = await createPeerConnection(config);
    _localStream = await navigator.mediaDevices.getUserMedia({'audio': true, 'video': false});
    for (final track in _localStream!.getTracks()) {
      await pc.addTrack(track, _localStream!);
    }
    pc.onIceCandidate = (candidate) {
      if (candidate.candidate == null) return;
      _sendSignal({
        'event': 'webrtc_ice',
        'peer_id': widget.peer.id,
        'call_id': _callId,
        'candidate': candidate.toMap(),
      });
    };
    pc.onTrack = (event) {
      if (event.streams.isNotEmpty) {
        _remoteStream = event.streams.first;
        setState(() => _callStatus = 'Audio connected');
      }
    };
    _peerConnection = pc;
    return pc;
  }

  Future<void> _startWebRtcOffer(int callId) async {
    final pc = await _ensurePeerConnection();
    final offer = await pc.createOffer({'offerToReceiveAudio': true, 'offerToReceiveVideo': false});
    await pc.setLocalDescription(offer);
    _sendSignal({
      'event': 'webrtc_offer',
      'peer_id': widget.peer.id,
      'call_id': callId,
      'description': offer.toMap(),
    });
  }

  Future<void> _acceptWebRtcCall(int callId) async {
    final pc = await _ensurePeerConnection();
    final remote = await pc.getRemoteDescription();
    if (remote == null) {
      _pendingAnswerCallId = callId;
      return;
    }
    _pendingAnswerCallId = null;
    final answer = await pc.createAnswer({'offerToReceiveAudio': true, 'offerToReceiveVideo': false});
    await pc.setLocalDescription(answer);
    _sendSignal({
      'event': 'webrtc_answer',
      'peer_id': widget.peer.id,
      'call_id': callId,
      'description': answer.toMap(),
    });
  }

  Future<void> _handleWebRtcOffer(Map<String, dynamic> data) async {
    final callId = data['call_id'];
    if (callId != null) setState(() => _callId = int.parse('$callId'));
    final description = data['description'] as Map<String, dynamic>?;
    if (description == null) return;
    final pc = await _ensurePeerConnection();
    await pc.setRemoteDescription(RTCSessionDescription(description['sdp'] as String?, description['type'] as String?));
    final pendingAnswer = _pendingAnswerCallId;
    if (pendingAnswer != null) {
      await _acceptWebRtcCall(pendingAnswer);
    }
  }

  Future<void> _handleWebRtcAnswer(Map<String, dynamic> data) async {
    final description = data['description'] as Map<String, dynamic>?;
    if (description == null || _peerConnection == null) return;
    await _peerConnection!.setRemoteDescription(RTCSessionDescription(description['sdp'] as String?, description['type'] as String?));
    setState(() => _callStatus = 'Audio connected');
  }

  Future<void> _handleWebRtcIce(Map<String, dynamic> data) async {
    final candidate = data['candidate'] as Map<String, dynamic>?;
    if (candidate == null || _peerConnection == null) return;
    await _peerConnection!.addCandidate(
      RTCIceCandidate(
        candidate['candidate'] as String?,
        candidate['sdpMid'] as String?,
        candidate['sdpMLineIndex'] as int?,
      ),
    );
  }

  void _sendSignal(Map<String, dynamic> payload) {
    _socket?.sink.add(jsonEncode(payload));
  }

  void _setLocalMute(bool muted) {
    final stream = _localStream;
    if (stream == null) return;
    for (final track in stream.getAudioTracks()) {
      track.enabled = !muted;
    }
  }

  Future<void> _disposeWebRtc() async {
    final local = _localStream;
    final remote = _remoteStream;
    _localStream = null;
    _remoteStream = null;
    _pendingAnswerCallId = null;
    for (final track in local?.getTracks() ?? <MediaStreamTrack>[]) {
      await track.stop();
    }
    for (final track in remote?.getTracks() ?? <MediaStreamTrack>[]) {
      await track.stop();
    }
    await local?.dispose();
    await remote?.dispose();
    await _peerConnection?.close();
    _peerConnection = null;
  }

  bool _isImageName(String name) {
    final lower = name.toLowerCase();
    return lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png') || lower.endsWith('.gif') || lower.endsWith('.webp') || lower.endsWith('.bmp');
  }
}

class _CallBanner extends StatelessWidget {
  const _CallBanner({required this.status, required this.muted, required this.onEnd, required this.onMute});

  final String status;
  final bool muted;
  final VoidCallback onEnd;
  final VoidCallback onMute;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: const Color(0xFF12352F),
      child: Row(
        children: [
          const Icon(Icons.call, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(status)),
          IconButton(onPressed: onMute, icon: Icon(muted ? Icons.mic_off : Icons.mic)),
          IconButton.filledTonal(onPressed: onEnd, icon: const Icon(Icons.call_end)),
        ],
      ),
    );
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
