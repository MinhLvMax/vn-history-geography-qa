import pandas as pd
from helper import *

history_data = read_json_file('history_books_structured.json')
df = pd.DataFrame(history_data)
print(df['paragraph_length'].describe())

# print(f"P90 = {df['paragraph_length'].quantile(0.90)}")
# print(f"P95 = {df['paragraph_length'].quantile(0.95)}")
# print(f"P99 = {df['paragraph_length'].quantile(0.99)}")

long_paragraph = df[df["paragraph_length"] == 3510]

print(
    long_paragraph[
        ["paragraph_content"]
    ].to_string(index=False)
)

print(f'{len(long_paragraph)=}')
