# bulk-operations

## Purpose

Lets users move data in and out of datasets (CSV/JSON import and export) and apply bulk updates/deletes by filter, with mapping previews and confirmation gates so naive users never bulk-mangle data by accident.

## ADDED Requirements

### Requirement: Bulk update by filter
The system SHALL update all rows matching a filter with a set of column values, defaulting to a dry-run preview; execution requires explicit confirmation and reports matched and updated counts.

#### Scenario: Dry-run preview
- **WHEN** update_rows is called with filter stage eq "Screened", set stage "Rejected", and dry_run true
- **THEN** the matched row ids are previewed with requires_confirmation true and nothing changes

#### Scenario: Bulk update confirmed
- **WHEN** the same call is repeated with confirm true
- **THEN** all matched rows are updated and the report states the updated count

### Requirement: Bulk delete by filter
The system SHALL delete all rows matching a filter after a preview and explicit confirmation, reporting the deleted count.

#### Scenario: Bulk delete confirmed
- **WHEN** delete_rows is called with filter experience lt 2 and confirm true
- **THEN** all matching rows are deleted and the deleted count is reported

### Requirement: CSV/JSON import
The system SHALL import rows from a CSV or JSON file in two steps: a mapping preview (file column to dataset column, unmatched file columns, missing required dataset columns) followed by a confirmed commit returning a per-row accepted/rejected report with plain-language reasons.

#### Scenario: Mapping preview
- **WHEN** import_rows is called with confirm false on a CSV whose columns match the dataset
- **THEN** the mapping is returned with requires_confirmation true and no rows are added

#### Scenario: Import with rejects
- **WHEN** import_rows commits 50 CSV rows of which 5 have invalid phones
- **THEN** 45 rows are added and the report lists the 5 rejected rows with reasons

#### Scenario: Missing file
- **WHEN** import_rows is called with a path that does not exist
- **THEN** an error names the missing file

### Requirement: Export
The system SHALL export rows (optionally filtered and projected) to a CSV or JSON file, returning the file path and row count.

#### Scenario: Export to CSV
- **WHEN** export_rows is called with format csv and filter stage eq "Applied"
- **THEN** a CSV file is written containing only matching rows and the response carries its path and row count
