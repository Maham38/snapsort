import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

class UploadItem {
  UploadItem(this.file);

  final PlatformFile file;
  UploadStatus status = UploadStatus.queued;
  double progress = 0;
  String? error;
}

enum UploadStatus { queued, uploading, complete, failed }

class PhotoUploadService {
  PhotoUploadService({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = _resolveUploadBaseUrl(baseUrl);

  final http.Client _client;
  final String _baseUrl;

  Future<String> _token() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) throw StateError('Sign in before uploading photos.');
    final token = await user.getIdToken();
    if (token == null || token.isEmpty) {
      throw StateError('Could not obtain an authentication token.');
    }

    return token;
  }

  Future<void> upload({
    required String eventId,
    required UploadItem item,
    required void Function(double progress) onProgress,
  }) async {
    final token = await _token();
    final path = item.file.path;
    if (path == null) throw StateError('Could not read ${item.file.name}.');
    final file = File(path);
    final sizeBytes = await file.length();
    final contentType = _contentType(item.file.name);
    final request = await _client.post(
      Uri.parse('$_baseUrl/api/v1/events/$eventId/uploads'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'filename': item.file.name,
        'content_type': contentType,
        'size_bytes': sizeBytes,
        'checksum': null,
      }),
    ).timeout(const Duration(seconds: 30));
    if (request.statusCode != 201) {
      throw PhotoUploadException(_detail(request.body, request.statusCode));
    }
    final upload = jsonDecode(request.body) as Map<String, dynamic>;
    final uploadClient = HttpClient();
    final uploadRequest = await uploadClient
        .putUrl(Uri.parse(upload['upload_url'] as String))
        .timeout(const Duration(seconds: 30));
    uploadRequest.headers.set(HttpHeaders.contentTypeHeader, contentType);
    final total = await file.length();
    var sent = 0;
    await for (final chunk in file.openRead()) {
      uploadRequest.add(chunk);
      sent += chunk.length;
      onProgress(total == 0 ? 1 : sent / total);
    }
    final uploadResponse = await uploadRequest.close().timeout(
      const Duration(minutes: 5),
    );
    if (uploadResponse.statusCode < 200 || uploadResponse.statusCode >= 300) {
      uploadClient.close();
      throw PhotoUploadException(
        'Storage upload failed (${uploadResponse.statusCode}).',
      );
    }
    uploadClient.close();
    final complete = await _client.post(
      Uri.parse('$_baseUrl/api/v1/photos/${upload['photo_id']}/complete'),
      headers: {'Authorization': 'Bearer $token'},
    ).timeout(const Duration(seconds: 30));
    if (complete.statusCode != 200) {
      throw PhotoUploadException(_detail(complete.body, complete.statusCode));
    }
  }

  String _contentType(String filename) {
    final extension = filename.split('.').last.toLowerCase();
    return switch (extension) {
      'png' => 'image/png',
      'webp' => 'image/webp',
      'jpg' || 'jpeg' => 'image/jpeg',
      _ => throw StateError('Unsupported image type: .$extension'),
    };
  }

  String _detail(String body, int statusCode) {
    try {
      return (jsonDecode(body) as Map<String, dynamic>)['detail'] as String? ??
          'Upload failed ($statusCode).';
    } on FormatException {
      return 'Upload failed ($statusCode).';
    }
  }
}

class PhotoUploadException implements Exception {
  const PhotoUploadException(this.message);

  final String message;

  @override
  String toString() => message;
}

String _resolveUploadBaseUrl(String? baseUrl) {
  final configured =
      baseUrl ?? const String.fromEnvironment('SNAPSORT_API_BASE_URL');
  if (configured.isNotEmpty) {
    final uri = Uri.tryParse(configured);
    if (uri != null && uri.scheme == 'https') return configured;
    if (const bool.fromEnvironment('dart.vm.product')) {
      throw StateError('Production API URL must use HTTPS.');
    }
  }
  if (const bool.fromEnvironment('dart.vm.product')) {
    throw StateError(
      'Configure SNAPSORT_API_BASE_URL with an HTTPS endpoint for release builds.',
    );
  }
  return configured.isEmpty ? 'http://10.0.2.2:8000' : configured;
}
