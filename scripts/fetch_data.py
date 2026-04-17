import pandas as pd


file_path = "data/raw/Stock Exchange KSE 100(Pakistan).csv"
df = pd.read_csv(file_path)

print(df.head())

print(df.info())

print(df.describe())