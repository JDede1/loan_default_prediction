#!/usr/bin/env python
"""
Generate dummy training + batch input CSVs for CI/CD tests.

- ✅ Matches schema of real project files
- ✅ Numeric-friendly values (no strings) so ML models can train
- ✅ Adds `loan_status` only to training CSV
"""

import pandas as pd
import numpy as np
import os

np.random.seed(42)
n_train = 200
n_batch = 100

# Shared features between batch_input and training
features = [
    "loan_amnt",
    "debt_settlement_flag_Y",
    "term",
    "issue_year",
    "int_rate",
    "grade",
    "total_rev_hi_lim",
    "revol_bal",
    "dti",
    "total_bc_limit",
    "fico_range_low",
    "bc_open_to_buy",
    "annual_inc",
    "tot_cur_bal",
    "avg_cur_bal",
    "mo_sin_old_rev_tl_op",
    "revol_util",
    "total_bal_ex_mort",
    "bc_util",
    "mo_sin_old_il_acct",
]

def make_dataframe(n_rows, include_target=False):
    df = pd.DataFrame({
        "loan_amnt": np.random.randint(1000, 35000, n_rows),
        "debt_settlement_flag_Y": np.random.randint(0, 2, n_rows),
        "term": np.random.choice([36, 60], n_rows),  # months
        "issue_year": np.random.randint(2000, 2024, n_rows),
        "int_rate": np.random.uniform(5, 30, n_rows),
        "grade": np.random.randint(1, 8, n_rows),  # numeric grade (A–G mapped to 1–7)
        "total_rev_hi_lim": np.random.randint(1000, 50000, n_rows),
        "revol_bal": np.random.randint(0, 50000, n_rows),
        "dti": np.random.uniform(0, 40, n_rows),
        "total_bc_limit": np.random.randint(1000, 40000, n_rows),
        "fico_range_low": np.random.randint(600, 850, n_rows),
        "bc_open_to_buy": np.random.randint(0, 20000, n_rows),
        "annual_inc": np.random.randint(20000, 120000, n_rows),
        "tot_cur_bal": np.random.randint(0, 200000, n_rows),
        "avg_cur_bal": np.random.randint(0, 20000, n_rows),
        "mo_sin_old_rev_tl_op": np.random.randint(0, 300, n_rows),
        "revol_util": np.random.uniform(0, 100, n_rows),
        "total_bal_ex_mort": np.random.randint(0, 200000, n_rows),
        "bc_util": np.random.uniform(0, 100, n_rows),
        "mo_sin_old_il_acct": np.random.randint(0, 300, n_rows),
    })

    if include_target:
        df["loan_status"] = np.random.choice([0, 1], n_rows, p=[0.7, 0.3])

    return df

# Ensure data/ dir exists
os.makedirs("data", exist_ok=True)

# Generate training data
train_df = make_dataframe(n_train, include_target=True)
train_path = "data/loan_default_selected_features_clean.csv"
train_df.to_csv(train_path, index=False)
print(f"✅ Training CSV saved to {train_path} (rows={len(train_df)}, cols={train_df.shape[1]})")

# Generate batch input data
batch_df = make_dataframe(n_batch, include_target=False)
batch_path = "data/batch_input.csv"
batch_df.to_csv(batch_path, index=False)
print(f"✅ Batch input CSV saved to {batch_path} (rows={len(batch_df)}, cols={batch_df.shape[1]})")
