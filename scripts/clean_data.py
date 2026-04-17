import pandas as pd
import numpy as np


file_path = "data/raw/Stock Exchange KSE 100(Pakistan).csv"
df = pd.read_csv(file_path)

cols=['Open','High','Low','Close','Change','Volume']

for col in cols:
    df[col]=df[col].str.replace(',','').astype(float)


df['Date']=pd.to_datetime(df['Date'])


print(df.dtypes)

print(df.head())
print(df.info())
print(df.describe())


df=df.sort_values(by='Date')
df=df.reset_index(drop=True)

print(df.isnull().sum())
print(df.head())
print(df.tail())

df.to_csv("data/processed/cleaned_data.csv",index=False)