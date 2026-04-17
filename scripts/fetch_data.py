# import pandas as pd


# file_path = "data/raw/Stock Exchange KSE 100(Pakistan).csv"
# df = pd.read_csv(file_path)

# print(df.head())

# print(df.info())

# print(df.describe())


import os
import pandas as pd
import requests

RAW_PATH = "data/raw/"
os.makedirs(RAW_PATH, exist_ok=True)

def fetch_psx_data():
    url = "https://example.com/psx_data.csv"  # replace with real source

    response = requests.get(url)

    if response.status_code == 200:
        with open(RAW_PATH + "psx_data.csv", "wb") as f:
            f.write(response.content)
        print("Data downloaded successfully!")
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    fetch_psx_data()