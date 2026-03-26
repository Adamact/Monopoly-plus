settings = {
    "player": {
        "start_balance": 30000,
        "max_shares": 4,
        "dividend_per_share": 0.15,  # 15% of rent per share held
    },
    "bank_loan": {
        "interest_rate": 0.10,  # 10% per lap around the board
        "min_loan": 500,
        "max_loan": 10000,
    },
    "distress": {
        "rent_penalty": 0.50,  # halves rent income
        "duration_rounds": 2,  # 2 rounds of distressed status
    },
}
