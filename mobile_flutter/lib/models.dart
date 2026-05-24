class MaviUser {
  const MaviUser({required this.id, required this.username, this.status = 'offline'});

  final int id;
  final String username;
  final String status;

  factory MaviUser.fromJson(Map<String, dynamic> json) {
    return MaviUser(
      id: json['id'] as int,
      username: json['username'] as String,
      status: json['status'] as String? ?? 'offline',
    );
  }
}

class MaviMessage {
  const MaviMessage({
    required this.id,
    required this.senderId,
    required this.receiverId,
    required this.content,
    required this.messageType,
    required this.timestamp,
    this.attachmentId,
    this.fileName,
    this.contentType,
  });

  final int id;
  final int senderId;
  final int receiverId;
  final String content;
  final String messageType;
  final String timestamp;
  final int? attachmentId;
  final String? fileName;
  final String? contentType;

  bool get isImage => (contentType ?? '').startsWith('image/');

  factory MaviMessage.fromJson(Map<String, dynamic> json) {
    return MaviMessage(
      id: json['id'] as int,
      senderId: json['sender_id'] as int,
      receiverId: json['receiver_id'] as int,
      content: json['content'] as String? ?? '',
      messageType: json['message_type'] as String? ?? 'text',
      timestamp: json['timestamp'] as String? ?? '',
      attachmentId: json['attachment_id'] as int?,
      fileName: json['file_name'] as String?,
      contentType: json['content_type'] as String?,
    );
  }
}
