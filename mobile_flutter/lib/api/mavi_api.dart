import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models.dart';

class MaviApi {
  MaviApi({String? baseUrl}) : baseUrl = baseUrl ?? const String.fromEnvironment('MAVI_API_BASE', defaultValue: 'http://10.0.2.2:8765');

  final String baseUrl;

  Uri _uri(String path, [Map<String, String>? query]) {
    return Uri.parse('$baseUrl$path').replace(queryParameters: query);
  }

  Map<String, String> _headers(String token) => {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};

  Future<String> login(String username, String password) async {
    final response = await http.post(
      _uri('/api/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    _ensureOk(response);
    return jsonDecode(response.body)['token'] as String;
  }

  Future<String> register(String username, String email, String password) async {
    final response = await http.post(
      _uri('/api/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'email': email, 'password': password}),
    );
    _ensureOk(response);
    return jsonDecode(response.body)['token'] as String;
  }

  Future<List<MaviUser>> search(String token, String query) async {
    final response = await http.get(_uri('/api/search', {'query': query}), headers: _headers(token));
    _ensureOk(response);
    final items = jsonDecode(response.body)['results'] as List<dynamic>;
    return items.map((item) => MaviUser.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<List<MaviMessage>> messages(String token, int peerId) async {
    final response = await http.get(_uri('/api/messages', {'peer_id': '$peerId'}), headers: _headers(token));
    _ensureOk(response);
    final items = jsonDecode(response.body)['items'] as List<dynamic>;
    return items.map((item) => MaviMessage.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<MaviMessage> sendMessage(String token, int peerId, String content, {int? attachmentId, String type = 'text'}) async {
    final response = await http.post(
      _uri('/api/messages'),
      headers: _headers(token),
      body: jsonEncode({'receiver_id': peerId, 'content': content, 'message_type': type, 'attachment_id': attachmentId}),
    );
    _ensureOk(response);
    return MaviMessage.fromJson(jsonDecode(response.body)['message'] as Map<String, dynamic>);
  }

  Future<int> uploadAttachment(String token, File file) async {
    final request = http.MultipartRequest('POST', _uri('/api/attachments'));
    request.headers['Authorization'] = 'Bearer $token';
    request.files.add(await http.MultipartFile.fromPath('file', file.path));
    final response = await http.Response.fromStream(await request.send());
    _ensureOk(response);
    return jsonDecode(response.body)['attachment']['id'] as int;
  }

  String attachmentUrl(int id) => '$baseUrl/api/attachments/$id';

  void _ensureOk(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(response.body);
    }
  }
}
