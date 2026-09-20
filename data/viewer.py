import pandas as pd
from helper import *
from data.config import Config

config_json = read_json_file('config.json')
history_data = read_json_file(config_json['structured'])
df = pd.DataFrame(history_data)
print(df['paragraph_length'].describe())

# print(f"P90 = {df['paragraph_length'].quantile(0.90)}")
# print(f"P95 = {df['paragraph_length'].quantile(0.95)}")
# print(f"P99 = {df['paragraph_length'].quantile(0.99)}")

# long_paragraph = df[df["paragraph_length"] == 3510]
#
# print(
#     long_paragraph[
#         ["paragraph_content"]
#     ].to_string(index=False)
# )
#
# print(f'{len(long_paragraph)=}')

df_sentences = df.explode("sentences", ignore_index=True)

df_sentences = pd.concat(
    [
        df_sentences.drop(columns=["sentences"]),
        df_sentences["sentences"].apply(pd.Series)
    ],
    axis=1
)

print(df_sentences.describe())
