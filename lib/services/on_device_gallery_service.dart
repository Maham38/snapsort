import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';
import 'package:photo_manager/photo_manager.dart';
import 'package:saver_gallery/saver_gallery.dart';

class DevicePhoto {
  const DevicePhoto({
    required this.id,
    required this.name,
    required this.asset,
  });

  final String id;
  final String name;
  final AssetEntity asset;
}

class SavedEventPhoto {
  const SavedEventPhoto({
    required this.eventId,
    required this.eventName,
    required this.photoId,
    required this.path,
  });

  factory SavedEventPhoto.fromJson(Map<String, dynamic> json) => SavedEventPhoto(
    eventId: json['event_id'] as String,
    eventName: json['event_name'] as String,
    photoId: json['photo_id'] as String,
    path: json['path'] as String,
  );

  final String eventId;
  final String eventName;
  final String photoId;
  final String path;

  Map<String, dynamic> toJson() => {
    'event_id': eventId,
    'event_name': eventName,
    'photo_id': photoId,
    'path': path,
  };
}

class OnDeviceGalleryService {
  Future<Directory> _photoDirectory() async {
    final root = await getApplicationDocumentsDirectory();
    final directory = Directory('${root.path}/SnapSortPhotos');
    await directory.create(recursive: true);
    return directory;
  }

  Future<List<SavedEventPhoto>> savedEventPhotos() async {
    final directory = await _photoDirectory();
    final index = File('${directory.path}/index.json');
    if (!await index.exists()) return [];
    final values = jsonDecode(await index.readAsString()) as List<dynamic>;
    return values
        .map((value) => SavedEventPhoto.fromJson(value as Map<String, dynamic>))
        .where((photo) => File(photo.path).existsSync())
        .toList();
  }

  Future<void> saveMatchedPhoto({
    required String eventId,
    required String eventName,
    required String photoId,
    required Uint8List bytes,
  }) async {
    final directory = await _photoDirectory();
    final path = '${directory.path}/$photoId.jpg';
    await File(path).writeAsBytes(bytes, flush: true);
    final photos = await savedEventPhotos();
    if (!photos.any((photo) => photo.photoId == photoId)) {
      photos.add(
        SavedEventPhoto(
          eventId: eventId,
          eventName: eventName,
          photoId: photoId,
          path: path,
        ),
      );
      await File('${directory.path}/index.json').writeAsString(
        jsonEncode(photos.map((photo) => photo.toJson()).toList()),
        flush: true,
      );
    }
    await saveRemoteImage(bytes, 'snapsort_$photoId.jpg');
  }

  Future<PermissionState> requestPermission() {
    return PhotoManager.requestPermissionExtend();
  }

  Future<List<DevicePhoto>> scan({int limit = 100}) async {
    final permission = await requestPermission();
    if (!permission.isAuth) {
      throw StateError(
        'Photo access permission is required to scan your device gallery.',
      );
    }
    final albums = await PhotoManager.getAssetPathList(
      type: RequestType.image,
      onlyAll: true,
    );
    if (albums.isEmpty) return [];
    final assets = await albums.first.getAssetListPaged(page: 0, size: limit);
    final seen = <String>{};
    return assets
        .where((asset) => seen.add(asset.id))
        .map(
          (asset) => DevicePhoto(
            id: asset.id,
            name: asset.title ?? 'photo_${asset.id}.jpg',
            asset: asset,
          ),
        )
        .toList();
  }

  Future<void> organize(List<DevicePhoto> photos) async {
    for (final photo in photos) {
      final bytes = await photo.asset.originBytes;
      if (bytes == null || bytes.isEmpty) {
        throw StateError(
          'Could not read ${photo.name} from the device gallery.',
        );
      }
      final result = await SaverGallery.saveImage(
        Uint8List.fromList(bytes),
        fileName: 'snapsort_${photo.id}.jpg',
        albumPath: 'SnapSort',
        skipIfExists: true,
      );
      if (!result.isSuccess) {
        throw StateError(
          result.errorMessage ?? 'Could not organize ${photo.name}.',
        );
      }
    }
  }

  Future<void> saveRemoteImage(Uint8List bytes, String fileName) async {
    final result = await SaverGallery.saveImage(
      bytes,
      fileName: fileName,
      albumPath: 'SnapSort',
      skipIfExists: true,
    );
    if (!result.isSuccess) {
      throw StateError(
        result.errorMessage ?? 'Could not save the matched photo.',
      );
    }
  }
}
