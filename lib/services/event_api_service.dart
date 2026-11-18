import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

class EventRecord {
  const EventRecord({
    required this.id,
    required this.name,
    required this.description,
    required this.eventCode,
    required this.status,
  });

  factory EventRecord.fromJson(Map<String, dynamic> json) => EventRecord(
    id: json['id'] as String,
    name: json['name'] as String,
    description: json['description'] as String?,
    eventCode: json['event_code'] as String,
    status: json['status'] as String,
  );

  final String id;
  final String name;
  final String? description;
  final String eventCode;
  final String status;
}

class PlanRecord {
  const PlanRecord({
    required this.tier,
    required this.maxPhotos,
    required this.maxStorageBytes,
    required this.maxMatchingSearches,
    required this.retentionDays,
    required this.priceCents,
    required this.currency,
  });

  factory PlanRecord.fromJson(Map<String, dynamic> json) => PlanRecord(
    tier: json['tier'] as String,
    maxPhotos: json['max_photos'] as int,
    maxStorageBytes: json['max_storage_bytes'] as int,
    maxMatchingSearches: json['max_matching_searches'] as int,
    retentionDays: json['retention_days'] as int,
    priceCents: json['price_cents'] as int,
    currency: json['currency'] as String,
  );

  final String tier;
  final int maxPhotos;
  final int maxStorageBytes;
  final int maxMatchingSearches;
  final int retentionDays;
  final int priceCents;
  final String currency;
}

class EventPlan {
  const EventPlan({
    required this.tier,
    required this.status,
    required this.expiresAt,
    required this.limits,
    required this.photoCount,
    required this.storageBytes,
    required this.matchingSearches,
  });

  factory EventPlan.fromJson(Map<String, dynamic> json) {
    final usage = json['usage'] as Map<String, dynamic>;
    return EventPlan(
      tier: json['tier'] as String?,
      status: json['status'] as String,
      expiresAt: json['expires_at'] as String?,
      limits: json['limits'] == null
          ? null
          : PlanRecord.fromJson(json['limits'] as Map<String, dynamic>),
      photoCount: usage['photo_count'] as int,
      storageBytes: usage['storage_bytes'] as int,
      matchingSearches: usage['matching_searches'] as int,
    );
  }

  final String? tier;
  final String status;
  final String? expiresAt;
  final PlanRecord? limits;
  final int photoCount;
  final int storageBytes;
  final int matchingSearches;
}

class CheckoutSession {
  const CheckoutSession({required this.checkoutUrl});

  factory CheckoutSession.fromJson(Map<String, dynamic> json) =>
      CheckoutSession(checkoutUrl: json['checkout_url'] as String);

  final String checkoutUrl;
}

class UploadedPhoto {
  const UploadedPhoto({
    required this.id,
    required this.eventId,
    required this.eventName,
    required this.photoUrl,
    required this.status,
  });

  factory UploadedPhoto.fromJson(Map<String, dynamic> json) => UploadedPhoto(
    id: json['id'] as String,
    eventId: json['event_id'] as String,
    eventName: json['event_name'] as String,
    photoUrl: json['photo_url'] as String,
    status: json['processing_status'] as String,
  );

  final String id;
  final String eventId;
  final String eventName;
  final String photoUrl;
  final String status;
}

class EventApiService {
  EventApiService({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = _resolveBaseUrl(baseUrl);

  final http.Client _client;
  final String _baseUrl;

  Future<Map<String, String>> _headers() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw StateError('Sign in before managing events.');
    }

    final token = await user.getIdToken();
    if (token == null || token.isEmpty) {
      throw StateError('Could not obtain an authentication token.');
    }
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  Future<List<EventRecord>> listEvents() async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/events'),
      headers: await _headers(),
    );
    _check(response);
    final values = jsonDecode(response.body) as List<dynamic>;
    return values
        .map((value) => EventRecord.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<EventPlan> getEventPlan(String eventId) async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/events/$eventId/plan'),
      headers: await _headers(),
    );
    _check(response);
    return EventPlan.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<CheckoutSession> createCheckout({
    required String eventId,
    required String tier,
  }) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/events/$eventId/checkout'),
      headers: await _headers(),
      body: jsonEncode({'tier': tier}),
    );
    _check(response);
    return CheckoutSession.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> updateRole(String role) async {
    final response = await _client.patch(
      Uri.parse('$_baseUrl/api/v1/me/role'),
      headers: await _headers(),
      body: jsonEncode({'role': role}),
    );
    _check(response);
  }

  Future<List<EventRecord>> listPhotographerEvents() async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/photographer/events'),
      headers: await _headers(),
    );
    _check(response);
    final values = jsonDecode(response.body) as List<dynamic>;
    return values
        .map((value) => EventRecord.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<List<UploadedPhoto>> listUploadedPhotos() async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/photographer/photos'),
      headers: await _headers(),
    );
    _check(response);
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => UploadedPhoto.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<EventRecord> joinPhotographerEvent(String code) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/photographer/events'),
      headers: await _headers(),
      body: jsonEncode({'event_code': code.trim().toUpperCase()}),
    );
    _check(response);
    return EventRecord.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<EventRecord> createEvent({
    required String name,
    String? description,
  }) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/events'),
      headers: await _headers(),
      body: jsonEncode({'name': name, 'description': description}),
    );
    _check(response);
    return EventRecord.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<EventRecord> joinEvent(String code) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/attendee/events'),
      headers: await _headers(),
      body: jsonEncode({'event_code': code.trim().toUpperCase()}),
    );
    _check(response);
    return EventRecord.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<List<EventRecord>> listAttendeeEvents() async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/attendee/events'),
      headers: await _headers(),
    );
    _check(response);
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => EventRecord.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<SelfieUpload> requestSelfieUpload(String eventId) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/attendee/events/$eventId/selfie-upload'),
      headers: await _headers(),
    );
    _check(response);
    return SelfieUpload.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> grantFaceConsent(String eventId) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/events/$eventId/consent'),
      headers: await _headers(),
      body: jsonEncode({'consent_type': 'face_matching'}),
    );
    _check(response);
  }

  Future<MatchingJob> createMatchingJob({
    required String eventId,
    required String storageKey,
  }) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/v1/events/$eventId/matching-jobs'),
      headers: await _headers(),
      body: jsonEncode({'selfie_storage_key': storageKey}),
    );
    _check(response);
    return MatchingJob.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<MatchingJob> getMatchingJob(String jobId) async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/matching-jobs/$jobId'),
      headers: await _headers(),
    );
    _check(response);
    return MatchingJob.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<List<MatchResult>> getMatchingResults(String jobId) async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/matching-jobs/$jobId/results'),
      headers: await _headers(),
    );
    _check(response);
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => MatchResult.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<List<MatchResult>> getGallery(String eventId) async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/v1/attendee/events/$eventId/gallery'),
      headers: await _headers(),
    );
    _check(response);
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => MatchResult.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<MatchResult> setFavorite({
    required String photoId,
    required bool favorite,
  }) async {
    final response = favorite
        ? await _client.post(
            Uri.parse('$_baseUrl/api/v1/photos/$photoId/favorite'),
            headers: await _headers(),
          )
        : await _client.delete(
            Uri.parse('$_baseUrl/api/v1/photos/$photoId/favorite'),
            headers: await _headers(),
          );
    _check(response);
    if (!favorite) {
      return MatchResult(
        photoId: photoId,
        similarity: 0,
        photoUrl: '',
        favorite: false,
      );
    }
    return MatchResult.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> uploadSelfie({
    required SelfieUpload upload,
    required PlatformFile file,
    void Function(double progress)? onProgress,
  }) async {
    final path = file.path;
    if (path == null) throw StateError('Could not read ${file.name}.');
    final request = await HttpClient().putUrl(Uri.parse(upload.uploadUrl));
    request.headers.set(HttpHeaders.contentTypeHeader, 'image/jpeg');
    final source = File(path);
    final total = await source.length();
    var sent = 0;
    await for (final chunk in source.openRead()) {
      request.add(chunk);
      sent += chunk.length;
      onProgress?.call(total == 0 ? 1 : sent / total);
    }
    final response = await request.close();
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw EventApiException('Selfie upload failed (${response.statusCode}).');
    }
  }

  Future<EventRecord> updateEvent({
    required String id,
    required String name,
    String? description,
  }) async {
    final response = await _client.patch(
      Uri.parse('$_baseUrl/api/v1/events/$id'),
      headers: await _headers(),
      body: jsonEncode({'name': name, 'description': description}),
    );
    _check(response);
    return EventRecord.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> deleteEvent(String id) async {
    final response = await _client.delete(
      Uri.parse('$_baseUrl/api/v1/events/$id'),
      headers: await _headers(),
    );
    _check(response);
  }

  void _check(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    var detail = 'Event request failed (${response.statusCode}).';
    try {
      detail =
          (jsonDecode(response.body) as Map<String, dynamic>)['detail']
              as String? ??
          detail;
    } on FormatException {
      // Keep the status-based message for non-JSON responses.
    }
    throw EventApiException(detail);
  }
}

class SelfieUpload {
  const SelfieUpload({required this.storageKey, required this.uploadUrl});
  factory SelfieUpload.fromJson(Map<String, dynamic> json) => SelfieUpload(
    storageKey: json['storage_key'] as String,
    uploadUrl: json['upload_url'] as String,
  );
  final String storageKey;
  final String uploadUrl;
}

class MatchingJob {
  const MatchingJob({
    required this.id,
    required this.status,
    this.errorMessage,
  });
  factory MatchingJob.fromJson(Map<String, dynamic> json) => MatchingJob(
    id: json['id'] as String,
    status: json['status'] as String,
    errorMessage: json['error_message'] as String?,
  );
  final String id;
  final String status;
  final String? errorMessage;
}

class MatchResult {
  const MatchResult({
    required this.photoId,
    required this.similarity,
    required this.photoUrl,
    required this.favorite,
  });
  factory MatchResult.fromJson(Map<String, dynamic> json) => MatchResult(
    photoId: json['photo_id'] as String,
    similarity: (json['similarity'] as num).toDouble(),
    photoUrl: json['photo_url'] as String,
    favorite: json['favorite'] as bool? ?? false,
  );
  final String photoId;
  final double similarity;
  final String photoUrl;
  final bool favorite;
}

class EventApiException implements Exception {
  const EventApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

String _resolveBaseUrl(String? baseUrl) {
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
