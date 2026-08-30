# row-search

## Purpose

Lets users find, filter, sort, paginate, fuzzy-match, and summarize rows without ever dumping an entire dataset into the conversation, keeping agent context small.

## ADDED Requirements

### Requirement: Filtered search
The system SHALL search rows with conditions of the form {column, op, value} supporting eq, ne, gt, gte, lt, lte, contains, in, between, is_empty, is_not_empty. Unknown columns and value types incompatible with the column type SHALL be rejected in plain language.

#### Scenario: Equality filter
- **WHEN** search_rows filters stage eq "Applied" on 10 rows where 4 match
- **THEN** exactly those 4 rows are returned and total is 4

#### Scenario: Date range filter
- **WHEN** search_rows filters applied_on between "2026-08-01" and "2026-08-31"
- **THEN** only rows whose date falls in the inclusive range are returned

#### Scenario: Unknown column
- **WHEN** a condition references column "emial"
- **THEN** an error is returned naming the unknown column and listing available columns

### Requirement: Fuzzy matching
The system SHALL support fuzzy matching on string and text columns (tolerant of minor typos and misspellings), returning matches ordered by similarity with a score.

#### Scenario: Typo-tolerant name search
- **WHEN** search_rows with fuzzy enabled searches "Rahual" against the name column containing "Rahul Sharma"
- **THEN** "Rahul Sharma" is returned with a similarity score

### Requirement: Sorting and pagination
The system SHALL sort results by one column ascending or descending and paginate with limit (default 20, maximum 100) and offset, returning total and next_offset (null when exhausted).

#### Scenario: Sorted first page
- **WHEN** 25 rows exist and search_rows sorts by applied_on descending with limit 20
- **THEN** the first 20 rows of the sorted order are returned with total 25 and next_offset 20

#### Scenario: Final page
- **WHEN** the same search is repeated with offset 20
- **THEN** the remaining 5 rows are returned with total 25 and next_offset null

### Requirement: Column projection
The system SHALL return only the requested columns when a projection is provided, always including row ids.

#### Scenario: Projected results
- **WHEN** search_rows is called with columns name and stage
- **THEN** each result contains id, name, and stage only

### Requirement: Dataset summaries
The system SHALL summarize a dataset returning row count, count/min/max/avg/sum for each numeric column, and value breakdowns for each enum column, without returning row payloads.

#### Scenario: Inventory totals
- **WHEN** summarize_dataset runs on a dataset with quantity (integer) and status (enum)
- **THEN** numeric stats for quantity and value counts for status are returned
