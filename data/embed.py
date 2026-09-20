import chromadb
from chromadb.utils import embedding_functions
from data.config import Config
from data.helper import read_json_file

# 1. Khởi tạo ChromaDB
client = chromadb.PersistentClient(path=Config.DATA_PATH / 'chroma_db')

# 2. Model embedding
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-m3"
)

config_json = read_json_file('config.json')
data_json = read_json_file(config_json.get('structured'))

# 3. Tạo collection
collection = client.get_or_create_collection(
    name="history",
    embedding_function=embedding_fn
)

# 4. Dữ liệu đã chunk sẵn
chunks = [
    row.get('paragraph_content')
    for row in data_json
]
print(chunks[:3])

# 5. Metadata tương ứng
metadatas = [
    {
        k: v for k, v in row.items()
        if k not in ["paragraph_content", "sentences"]
    }
    for row in data_json
]
print(metadatas[:3])

# 6. ID duy nhất cho từng chunk
ids = [
    row.get('paragraph_id')
    for row in data_json
]
print(ids[:3])

# 7. Lưu vào ChromaDB
from tqdm import tqdm

BATCH_SIZE = 100

for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Embedding"):
    batch_ids = ids[i:i + BATCH_SIZE]
    batch_documents = chunks[i:i + BATCH_SIZE]
    batch_metadatas = metadatas[i:i + BATCH_SIZE]

    existing = collection.get(ids=batch_ids)["ids"]
    existing = set(existing)

    new_data = [
        (id_, doc, meta)
        for id_, doc, meta in zip(
            batch_ids,
            batch_documents,
            batch_metadatas
        )
        if id_ not in existing
    ]

    if new_data:
        new_ids, new_documents, new_metadatas = zip(*new_data)

        collection.add(
            ids=list(new_ids),
            documents=list(new_documents),
            metadatas=list(new_metadatas)
        )
