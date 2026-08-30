# row-management

## Purpose

Lets users add, read, update, validate, and delete rows against a dataset's schema, with Google-Forms-style typed validation, plain-language error reporting, and confirmation-gated deletion over safe atomic JSON storage.

## ADDED Requirements

### Requirement: Row addition
The system SHALL add one or more rows to a dataset in a single call (batch cap 100), validating each row against the dataset schema and returning a per-row report with status, generated row id, and plain-language errors.

#### Scenario: Add a valid row
- **WHEN** add_rows is called with one row of valid values
- **THEN** the row is stored with a generated id and the report marks it added

#### Scenario: Mixed batch
- **WHEN** add_rows is called with 3 rows where row 2 has phone "abc"
- **THEN** rows 1 and 3 are added, row 2 is rejected with a message naming the column, and the report shows one failure

#### Scenario: Batch cap enforced
- **WHEN** add_rows is called with 150 rows
- **THEN** an error is returned stating the 100-row cap and no rows are added

### Requirement: Typed validation
The system SHALL validate row values against column types before storing: string, text, boolean, integer, float, phone (10-digit Indian mobile with optional +91 or 0 prefix), date (ISO 8601 YYYY-MM-DD), enum (one of the column options). Required columns must be present and non-empty; unknown columns are rejected with the list of available columns; min/max and pattern constraints are enforced.

#### Scenario: Phone accepted
- **WHEN** a row has phone "9876543210" or "+919876543210"
- **THEN** both rows validate

#### Scenario: Phone rejected
- **WHEN** a row has phone "12345"
- **THEN** validation fails with a message explaining the expected phone format

#### Scenario: Enum rejection
- **WHEN** a row sets stage to "Hired" when options are Applied, Screened, Rejected
- **THEN** the row is rejected with a message listing the valid options

#### Scenario: Unknown column rejected
- **WHEN** a row contains column "emial"
- **THEN** it is rejected with the available column names listed

#### Scenario: Missing required column
- **WHEN** a row omits a required column
- **THEN** it is rejected naming the missing column

### Requirement: Row retrieval
The system SHALL return a single row by id with all columns, or only the requested column projection (id always included).

#### Scenario: Full row
- **WHEN** get_row is called with a valid id
- **THEN** the row is returned with all its columns

#### Scenario: Projected row
- **WHEN** get_row is called with columns name and stage
- **THEN** only id, name, and stage are returned

#### Scenario: Unknown id
- **WHEN** get_row is called with an id that does not exist
- **THEN** an error is returned naming the missing id

### Requirement: Row update
The system SHALL update rows by id(s), validating changed values against the schema, applying only the provided columns (partial update) and leaving other columns unchanged.

#### Scenario: Partial update
- **WHEN** update_rows sets stage "Rejected" on one row id
- **THEN** only stage changes on that row

#### Scenario: Invalid update rejected
- **WHEN** update_rows sets a float column to "senior"
- **THEN** that row is not changed and the report carries a plain-language type error

### Requirement: Row deletion
The system SHALL delete rows by id(s) only after a preview and explicit confirmation.

#### Scenario: Delete without confirmation
- **WHEN** delete_rows is called with confirm false
- **THEN** a preview listing affected row ids is returned with requires_confirmation true and nothing is deleted

#### Scenario: Delete confirmed
- **WHEN** delete_rows is re-invoked with confirm true
- **THEN** the rows are removed and get_row on those ids errors

### Requirement: Validation without saving
The system SHALL validate rows against a dataset schema and return per-row results without storing anything.

#### Scenario: Dry validation
- **WHEN** validate_rows is called with one invalid row
- **THEN** the report marks it invalid with reasons and the dataset row count is unchanged

### Requirement: Atomic JSON storage
The system SHALL persist each dataset as schema.json plus rows.json under data/<dataset>/, writing files atomically so a failed or interrupted write never leaves partial content.

#### Scenario: Repeated writes stay consistent
- **WHEN** rows.json is written twice in succession
- **THEN** the file always contains complete, parseable JSON reflecting the latest state
