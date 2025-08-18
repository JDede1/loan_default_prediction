import requests

url = "http://localhost:5001/invocations"

payload = {
    "dataframe_split": {
        "columns": [
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
        ],
        "data": [
            [
                15000,
                False,
                3.610917912644224,
                2016,
                7.99,
                1,
                10.448743588106623,
                9.94352523956766,
                3.096482176654134,
                9.957075711706056,
                6.54534966033442,
                8.319229938632326,
                11.156264806643742,
                10.430727717570214,
                7.597897950521784,
                5.123963979403259,
                55.7,
                10.430727717570214,
                79.2,
                120,
            ]
        ],
    }
}

response = requests.post(url, json=payload)
print("Prediction:", response.json())
