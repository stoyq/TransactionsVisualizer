---
name: process-transactions
description: Coordinate this project's transaction workflow from copied TD Visa data through combining, merchant normalization, and validation. Use for an end-to-end transaction processing run or a requested subset of these stages.
---

# Process transactions

Follow the enabled stages below in order. This file is an editable workflow:
the user can change its inputs, enable future stages, or request only part of a run.
Resolve project paths from the repository root. A request to edit this template
does not itself request a data-processing run.

## Configuration

| Setting | Current value |
| --- | --- |
| Account | TD Visa (`td_visa`) |
| Year | 2026 |
| Data folder | `data/raw/2026/TD/Visa/` |
| Raw copied input | `manual_copied_from_pdf.csv` |
| Converted intermediate | `manual_copied_from_pdf_converted.csv` |
| Combined intermediate | `combined_2026_visa.csv` |
| Merchant reference | Existing `combined_2026_visa_normalized.csv` |
| Final output | `combined_2026_visa_normalized.csv` |
| Enabled stages | Convert, combine, normalize, validate, summarize |
| Optional stages | Categorize and report: disabled until configured |

These settings document the current workflow; editing this table does not change
the scripts. The converter currently fixes the year to 2026. The combine script
hardcodes its input list, output path, and data source. For a different account,
year, or file set, inspect and align the relevant script settings before running.
Do not silently process another year as 2026.

## Before running

- Read the requested stages and inspect the input files and script settings.
- The combine script's `INPUT_FILES` is the authoritative list: currently six
  `accountactivity*.csv` exports plus the converted intermediate. Do not glob in
  previous combined or normalized outputs.
- Confirm required inputs exist. The converted intermediate may be absent if
  the conversion stage will create it. If a required input is missing, report
  the missing path and stop the dependent stages rather than creating partial output.
- Load the previous normalized CSV's merchant mappings before regenerating it.
  Preserve a timestamped sibling copy of that existing final file for experiments.
  If no reference exists, follow the normalization skill's first-run guidance.
- A full run may regenerate the configured intermediate and final outputs. Keep
  raw source files intact. Continue through enabled stages without asking for
  confirmation between routine steps.

## 1. Convert copied PDF transactions

Run from the project root:

```powershell
python misc_scripts/convert_td_visa.py
```

Input: the raw copied CSV. Output: the converted intermediate, with four columns
and no headers: date, description, debit, credit.

Verify that each input transaction produces one row, the first date is retained
as `MM/DD/2026`, posting dates are omitted, description lines are joined, and
negative amounts become positive credits. Stop dependent stages if conversion fails.

## 2. Combine bank exports and converted transactions

Run:

```powershell
python misc_scripts/combine_td_visa.py
```

Output: the combined intermediate with this header:

```text
date,data_source,description,description_normalized,debit,credit,category,subcategory
```

Verify that the transaction count equals the sum of nonblank rows in the configured
inputs. Preserve each input's date, description, debit, and credit in input-list
order; discard only the bank exports' fifth column. Set `data_source` to `td_visa`,
copy the original description into `description_normalized`, and leave category
and subcategory blank. Preserve duplicates.

## 3. Normalize merchants

Read and follow [normalize-transactions](../normalize-transactions/SKILL.md).
Pass the combined intermediate as input, the saved prior merchant mappings as
reference, and the configured final output path as destination.

Use LLM judgment for new merchant variants. Do not create a normalization script
unless requested. Preserve accepted mappings, and leave ambiguous new descriptions
unchanged while listing them for review. Ambiguous merchant names alone do not
block completion of the remaining valid rows.

## 4. Optional categorization — disabled

Before enabling this stage, define an allowed category/subcategory list, an
accepted merchant-to-category reference, and a destination for categorized output.
Then link the categorization instructions here. Until configured and enabled,
leave category and subcategory blank; do not invent a taxonomy.

## 5. Validate final output

- Require the eight-column schema above and the same transaction count as the
  combined intermediate. Compare parsed CSV fields, not raw quoting or line endings.
- Verify every field outside `description_normalized` matches the corresponding
  combined input field, including row order, dates, amounts, and blank categories.
- Check consistent merchant mappings as specified by the normalization skill.
- Calculate debit and credit totals separately with exact decimal arithmetic and
  confirm they match the combined input. Do not count the header as a transaction.
- Derive expected counts from the current inputs; do not assume the original
  730-transaction dataset size is permanent.

If validation fails, identify the stage and discrepancy, correct it within the
requested scope, and rerun the affected stages. Do not describe unvalidated output
as complete. If a correction requires missing information, report the blocker and
the last successfully verified stage.

## 6. Summarize the run

Report stages completed or skipped, final output path, transaction count, debit
and credit totals, distinct descriptions before and after normalization, new
merchant mappings, and any unresolved descriptions. Include the backup path if
one was created.

## 7. Optional spending report — disabled

Before enabling, specify the reporting period, metrics, destination, and treatment
of payments, refunds, and fees. Add reporting instructions or a script reference
here. Dashboard updates and publishing are outside the default workflow.

## Example requests

Full run:

> Read `skills/process-transactions/SKILL.md` and run its enabled stages for
> my current TD Visa files. Summarize the results and any uncertain merchant names.

Normalization only:

> Follow `skills/process-transactions/SKILL.md`, starting at normalization.
> Use the existing combined CSV and skip conversion and combining.

Planning only:

> Read `skills/process-transactions/SKILL.md` and explain which files each
> enabled stage would read and write. Do not run the workflow yet.
