import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'phonics_catalog.dart';

class PhonicsRepository {
  const PhonicsRepository({this.assetPath = 'assets/phonics/catalog.json'});

  final String assetPath;

  Future<PhonicsCatalog> loadCatalog() async {
    final raw = await rootBundle.loadString(assetPath);
    return PhonicsCatalog.parse(raw);
  }
}

final phonicsRepositoryProvider = Provider<PhonicsRepository>(
  (ref) => const PhonicsRepository(),
);

final phonicsCatalogProvider = FutureProvider<PhonicsCatalog>((ref) {
  return ref.watch(phonicsRepositoryProvider).loadCatalog();
});
