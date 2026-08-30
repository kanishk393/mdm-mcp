# dataset-management

## Purpose

Lets users create, inspect, reshape, and delete datasets with user-defined typed columns — the schema-building surface that replaces spreadsheet headers and Google-Forms-style form building, driven entirely through conversation.

## ADDED Requirements

### Requirement: Dataset creation
The system SHALL create a dataset with a unique name, optional description, and user-defined typed columns. Column types: string, text, boolean, integer, float, phone, date, enum. Column attributes: required, default, min/max (numeric columns), pattern (string/text columns), options (enum columns).

#### Scenario: Create a candidates dataset
- **WHEN** create_dataset is called with name "Candidates" and columns name/string(required), phone/phone, experience/float, stage/enum(options: Applied, Screened, Rejected), applied_on/date
- **THEN** the dataset is created and list_datasets shows it with 0 rows and its column summary

#### Scenario: Reject a duplicate column name
- **WHEN** create_dataset is called with two columns both named "name"
- **THEN** an error is returned naming the duplicate column and no dataset is created

#### Scenario: Reject an enum column without options
- **WHEN** create_dataset is called with an enum column whose options list is empty
- **THEN** an error is returned explaining enum columns need at least one option and no dataset is created

#### Scenario: Reject a duplicate dataset name
- **WHEN** create_dataset is called with a name that already exists (case-insensitive)
- **THEN** an error is returned and the existing dataset is unchanged

### Requirement: Dataset listing
The system SHALL list all datasets with row count and a name:type column summary, paginated with limit (default 20, maximum 100) and offset, returning total and next_offset (null when exhausted).

#### Scenario: List datasets paginated
- **WHEN** 3 datasets exist and list_datasets is called with limit 2
- **THEN** 2 datasets are returned with total 3 and next_offset 2

### Requirement: Dataset description
The system SHALL describe a dataset returning full column definitions (type and set constraints), row count, and optional sample rows capped at 5.

#### Scenario: Describe without samples
- **WHEN** describe_dataset is called without sample_rows
- **THEN** column definitions and row count are returned with no row payloads

#### Scenario: Describe with samples
- **WHEN** describe_dataset is called with sample_rows 3 on a dataset holding 10 rows
- **THEN** exactly 3 rows are returned, each with its id

#### Scenario: Unknown dataset
- **WHEN** describe_dataset is called with a dataset name that does not exist
- **THEN** an error is returned naming the missing dataset and listing available dataset names

### Requirement: Column addition
The system SHALL add a typed column to an existing dataset, backfilling all existing rows with the column default, or null when no default is set.

#### Scenario: Add a column with a default
- **WHEN** add_column adds stage/enum with default "Applied" to a dataset with 12 rows
- **THEN** describe_dataset shows the new column and all 12 rows carry stage "Applied"

#### Scenario: Add a column that already exists
- **WHEN** add_column is called with a column name already present
- **THEN** an error is returned and the schema is unchanged

### Requirement: Column update
The system SHALL update a column's type, constraints, or name. Existing rows SHALL be revalidated against the new definition; offending rows SHALL be reported per row id with their values preserved (no data dropped).

#### Scenario: Tighten a numeric column
- **WHEN** update_column sets max_value 10 on a float column and 3 rows exceed it
- **THEN** the definition is updated, the 3 offending row ids are reported with their values intact, and valid rows are untouched

#### Scenario: Rename a column
- **WHEN** update_column renames "name" to "full_name"
- **THEN** all rows expose the value under "full_name" and "name" no longer exists

### Requirement: Column removal
The system SHALL remove a column only after a preview and explicit confirmation; on confirmation the column and its values are dropped from every row.

#### Scenario: Remove column without confirmation
- **WHEN** remove_column is called with confirm false
- **THEN** a preview is returned with requires_confirmation true and no data changes

#### Scenario: Remove column confirmed
- **WHEN** remove_column is re-invoked with confirm true
- **THEN** the column no longer appears in describe_dataset and no row contains it

### Requirement: Dataset deletion
The system SHALL delete a dataset and all its rows only after a preview (name, row count, column count) and explicit confirmation.

#### Scenario: Delete dataset without confirmation
- **WHEN** delete_dataset is called with confirm false
- **THEN** a preview is returned with requires_confirmation true and nothing is deleted

#### Scenario: Delete dataset confirmed
- **WHEN** delete_dataset is re-invoked with confirm true
- **THEN** the dataset no longer appears in list_datasets
