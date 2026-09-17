---
name: normalize-transactions
description: Normalize merchant descriptions in this project's transaction CSVs, reusing previously accepted names and preserving all other transaction fields. Use when asked to normalize or consolidate merchant names, not to categorize transactions or combine source files.
---

# Normalize transaction descriptions

Use LLM judgment to identify merchant variants. Do not create a normalization
script unless requested. File tools may be used to read, apply the chosen mappings,
and validate the CSV; merchant decisions should come from reviewing the descriptions.

## Project files

Resolve these paths from the project root, not this skill's directory:

- Default input: `data/raw/2026/TD/Visa/combined_2026_visa.csv`
- Existing merchant reference: `data/raw/2026/TD/Visa/combined_2026_visa_normalized.csv`
- Default output: a sibling file named `<input_stem>_normalized.csv`.

Use user-specified paths when supplied. Read the existing reference before replacing
an output at that same path. The reference contains previously accepted
`description` / `description_normalized` pairs; reuse those names for matching
descriptions and clearly matching new variants. If a separate accepted merchant
alias file is provided, use it as the reference instead. Report conflicting mappings.
If no reference is available, proceed with the naming rules below and disclose that
prior decisions could not be reused. These data files are gitignored and may not
be present in another checkout.

## Naming decisions

- Review distinct descriptions together so repeated merchants get consistent names.
- Group branches of the same merchant under one name. Remove store IDs, city and
  branch suffixes, phone numbers, order IDs, and payment processor prefixes when
  the remaining merchant identity is clear.
- Use readable capitalization and preserve meaningful brand spelling. Reuse the
  reference's spelling rather than renaming established merchants for style.
- Examples of accepted groupings: `AMZN Mktp CA*...` and `Amazon.ca*...` become
  `Amazon`; Starbucks store variants become `Starbucks`; numbered and branch
  variants of `SQ *STEVE'S POKE...` become `Steve's Poke Bar`.
- `BEAN AROUND WORLD UBC` and `BEAN AROUND THE WORLD` become
  `Bean Around the World`. `SQ *MO7SCOFFEE` becomes `MO7S Coffee`.
- Keep distinct services separate: `UBC Parking`, `UBC Recreation`, and
  `UBC Bookstore`; also `Google One` and `YouTube Premium`.
- Keep transaction types distinct: `Credit Card Payment`,
  `Preauthorized Credit Card Payment`, `Rewards Redemption`, `Annual Fee`,
  and `Annual Fee Rebate`.
- Do not merge businesses just because their names are similar, or guess the
  missing identity of a truncated description. Leave uncertain new descriptions
  unchanged in the normalized column and list them for review. For example,
  `UNIVERSITY OF BRITISH` does not establish a specific UBC service.

## Output and verification

Preserve these eight columns and their order:

```text
date,data_source,description,description_normalized,debit,credit,category,subcategory
```

Change only `description_normalized`. Preserve all other field values, row order,
and duplicates. Do not categorize, deduplicate, sort, change amounts, or alter dates.
Keep the input intact and write a separate output CSV with valid CSV escaping.

Before reporting completion, verify:

- The output has the same headers, transaction count, and eight fields per row.
- Every field outside `description_normalized` matches the corresponding input field.
- Each distinct original description has one consistent normalized name.
- Previously accepted mappings remain consistent unless the user requested a correction.

Report the output path, transaction count, distinct description counts before and
after, notable groupings, and uncertain or conflicting mappings. When a prior
reference exists, emphasize newly encountered variants and new merchant decisions.

## Example request

> Read `skills/normalize-transactions/SKILL.md` and follow it to normalize
> `data/raw/2026/TD/Visa/combined_2026_visa.csv`. Use the existing normalized CSV
> as the merchant reference, regenerate the normalized output, and summarize new mappings.
