import '../../../core/api_client.dart';

class BucketInfo {
  const BucketInfo({required this.id, required this.grade, required this.schoolYear, required this.status});

  factory BucketInfo.fromJson(Map<String, dynamic> j) => BucketInfo(
        id: (j['id'] as num).toInt(),
        grade: (j['grade'] as num?)?.toInt() ?? 0,
        schoolYear: '${j['school_year'] ?? ''}',
        status: '${j['status'] ?? ''}',
      );

  final int id;
  final int grade;
  final String schoolYear;
  final String status; // 'active' | 'archived'

  bool get isActive => status == 'active';
}

List<BucketInfo> parseBuckets(Object? data) {
  final list = asList(data);
  return [for (final b in list.whereType<Map>()) BucketInfo.fromJson(Map<String, dynamic>.from(b))];
}
