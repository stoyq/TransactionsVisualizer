# Transactions Visualizer

A Shiny for Python app to explore and visualize personal transaction data.

**Live dashboard:** https://019cd142-798e-34da-392d-0d9d66b6352c.share.connect.posit.cloud

![App snapshot](images/snapshots/2026-03-08.png)

## Setup

1. Clone the repo and create the conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate transactionsViz
   ```

2. Create a `.env` file in the project root:
   ```
   GDRIVE_FILE_ID=your_google_drive_file_id_here
   ```

3. Run the app:
   ```bash
   shiny run src/app.py
   ```

## Data

Place `transactions_2025.csv` in `data/processed/` for local development. The app falls back to Google Drive when the local file is not found (used on deployment).

## Deployment

Deployed on [Posit Connect](https://posit.co/products/cloud/connect/). Set `GDRIVE_FILE_ID` as a deployment environment variable — no `.env` file needed on the server.
