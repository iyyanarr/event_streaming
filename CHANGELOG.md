# Event Streaming App Changelog

All notable changes to this project will be documented in this file.

Format: Keep a reverse chronological order. Use ISO dates (YYYY-MM-DD). Follow semantic versioning (MAJOR.MINOR.PATCH).

## [Unreleased]
### Added
- Placeholder for upcoming changes.
- (Planned) Bulk validation endpoint placeholder.

### Changed
- Pending.
- UI: CSV import dialog clarifies accepted header variants.
- SPP Item Mapping UI: Removed automatic consumer field auto-fill (now requires explicit CSV or manual entry) to prevent overwriting distinct mappings.

### Fixed
- Pending.
- SPP Item Mapping: Imported CSV rows not appearing immediately in child table (now forces frm.reload_doc after import).
- SPP Item Mapping: CSV importer sometimes mapped both producer and consumer to same column when headers ambiguous (added distinct column detection + safeguards + debug info).

### Removed
- Auto-fill logic that copied producer_item_code into consumer_item_code on edit (eliminated to avoid silent data corruption during import/render race).

## [1.0.0] - 2025-09-04
### Summary
Initial formalized changelog entry. Major terminology refactor aligning SPP mappings with producer/consumer naming. Backward-compatible CSV import enhancements and UI adjustments.

### Added
- CHANGELOG.md with structured sections and contribution guidelines.
- Migration patch: `event_streaming/patches/v1_0/migrate_spp_mapping_terminology.py` to transition legacy source/target fields to producer/consumer across SPP mapping DocTypes.
- Backward-compatible CSV header detection supporting legacy and new headers (old_item_code / new_item_code, source_item_code / target_item_code, producer_item_code / consumer_item_code, "Producer Item Code" / "Consumer Item Code").
- Validation preventing duplicate `producer_item_code` entries in SPP Item Mapping lines.
- Automatic population of `consumer_item_code` when left blank in the UI.

### Changed
- Renamed all SPP mapping DocType fields:
  - Item: `source_item_code` → `producer_item_code`, `target_item_code` → `consumer_item_code`.
  - Site-level fields: `source_site` / `target_site` → `producer_site` / `consumer_site` (Item, Warehouse, Company, etc.).
  - Warehouse mapping detail: `source_warehouse` → `producer_warehouse`, `target_warehouse` → `consumer_warehouse`.
- Updated Python module `spp_item_mapping.py` to use new field names and improved import function.
- Updated UI script `spp_item_mapping.js` to reflect new terminology (producer/consumer) and export CSV header adjustments.
- Export CSV now emits headers: `producer_item_code,consumer_item_code,item_group,is_active,notes`.
- Integration function `apply_spp_mappings` continues to operate with new field names.

### Fixed
- CSV import failures caused by mismatch between UI (legacy field names) and DocType new fields.
- Potential silent duplication by enforcing duplicate check on `producer_item_code` instead of legacy fields.

### Removed
- Legacy references to `source_item_code` / `target_item_code` in active logic paths.

### Migration Notes
- Run standard bench migrate to apply patch.
- Existing data auto-migrated if legacy columns still present.
- No manual intervention required unless custom scripts referenced old field names.

### Backward Compatibility
- CSV import accepts legacy headers; output/export standardized to new headers.
- Getter method `get_target_item_code` name retained for compatibility though it now returns consumer item code.

### Follow-Up Tasks (Not Yet Implemented)
- Add similar backward-compatible refactors for Supplier, Account mappings if still using legacy terms anywhere.
- Add automated tests for mixed-header CSV import scenarios.
- Performance benchmark automation in a scheduled job.

---

## Contribution Guidelines for Future Entries
1. Add new changes under [Unreleased]. Do not create a release section until deployment is confirmed.
2. Group entries under: Added / Changed / Fixed / Removed / Security / Deprecated / Migration.
3. After release:
   - Create new version section with date.
   - Move all [Unreleased] entries into that section.
   - Reset [Unreleased] section placeholders.
4. Keep bullet points concise and action-oriented.

Example future entry under Unreleased:
```
### Added
- Bulk validation endpoint for all SPP mappings.
```

[1.0.0]: https://example.com/event_streaming/releases/1.0.0 (placeholder)