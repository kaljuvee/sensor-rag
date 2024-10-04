import os
from dotenv import load_dotenv
import pypdf
import pandas as pd
import pyodbc
from azure.storage.blob import BlobServiceClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
)
import openai
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.cosmos import CosmosClient
import numpy as np

# Load environment variables
load_dotenv()

# Azure Blob Storage settings
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "pdfs"

# MS SQL Database settings
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

# Azure AI Search settings
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("SEARCH_KEY")
SEARCH_INDEX_NAME = "rag-index"

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_DIMENSION = 1536  # Dimension of the OpenAI ada-002 model

# Azure OpenAI Service settings
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Cosmos DB settings
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE_NAME = "SensorDataDB"
COSMOS_CONTAINER_NAME = "SensorData"

# Choose the embedding and search method
USE_AZURE_OPENAI = os.getenv("USE_AZURE_OPENAI", "False").lower() == "true"

# Initialize Blob Storage client
blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
blob_container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

# Initialize Azure AI Search clients
search_credential = AzureKeyCredential(SEARCH_KEY)
search_index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=search_credential)
search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=SEARCH_INDEX_NAME, credential=search_credential)

# Initialize OpenAI or Azure OpenAI client
if USE_AZURE_OPENAI:
    openai_client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version="2023-05-15",
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
else:
    openai.api_key = OPENAI_API_KEY

# Initialize Cosmos DB client
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
cosmos_database = cosmos_client.create_database_if_not_exists(id=COSMOS_DATABASE_NAME)
cosmos_container = cosmos_database.create_container_if_not_exists(
    id=COSMOS_CONTAINER_NAME,
    partition_key="/sensor_id",
    offer_throughput=400
)

def create_search_index():
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="text", type=SearchFieldDataType.String),
        SearchableField(name="metadata", type=SearchFieldDataType.String),
        SimpleField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    vector_search_dimensions=EMBEDDING_DIMENSION, vector_search_configuration="default")
    ]
    vector_search = VectorSearch(
        algorithm_configurations=[
            VectorSearchAlgorithmConfiguration(
                name="default",
                kind="hnsw",
                hnsw_parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ]
    )
    index = SearchIndex(name=SEARCH_INDEX_NAME, fields=fields, vector_search=vector_search)
    result = search_index_client.create_or_update_index(index)
    print(f"Index {result.name} created or updated")

def process_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        pdf_reader = pypdf.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def upload_pdf_to_blob(pdf_path):
    blob_name = os.path.basename(pdf_path)
    blob_client = blob_container_client.get_blob_client(blob_name)
    with open(pdf_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    return blob_client.url

def get_embedding(text):
    if USE_AZURE_OPENAI:
        response = openai_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return response.data[0].embedding
    else:
        response = openai.Embedding.create(input=text, model=EMBEDDING_MODEL)
        return response['data'][0]['embedding']

def store_document(id, text, embedding, metadata):
    search_client.upload_documents([{
        "id": id,
        "text": text,
        "embedding": embedding,
        "metadata": str(metadata)
    }])

def process_and_store_pdf(pdf_path):
    text = process_pdf(pdf_path)
    blob_url = upload_pdf_to_blob(pdf_path)
    embedding = get_embedding(text)
    store_document(
        id=os.path.basename(pdf_path),
        text=text,
        embedding=embedding,
        metadata={"type": "pdf", "url": blob_url}
    )

def get_sql_data():
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD}')
    query = "SELECT * FROM SensorData"  # Adjust this query as needed
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def load_sql_data_to_cosmos():
    df = get_sql_data()
    for _, row in df.iterrows():
        cosmos_container.upsert_item({
            "id": str(row['id']),
            "sensor_id": str(row['sensor_id']),
            "timestamp": str(row['timestamp']),
            "value": row['value']
        })
    print(f"Loaded {len(df)} records into Cosmos DB")

def process_and_store_sensor_data():
    query = "SELECT * FROM c"
    items = list(cosmos_container.query_items(query=query, enable_cross_partition_query=True))
    
    for item in items:
        text = f"Sensor {item['sensor_id']} reading: {item['value']} at {item['timestamp']}"
        embedding = get_embedding(text)
        store_document(
            id=f"sensor_{item['sensor_id']}_{item['timestamp']}",
            text=text,
            embedding=embedding,
            metadata={"type": "sensor", "sensor_id": item['sensor_id']}
        )

def semantic_search(query, top_k=5):
    query_vector = get_embedding(query)
    results = search_client.search(
        search_text=query,
        vector=query_vector,
        top_k=top_k,
        vector_fields="embedding",
        select="id,text,metadata"
    )
    return results

def generate_response(query, context):
    if USE_AZURE_OPENAI:
        response = openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the question."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
            ]
        )
        return response.choices[0].message.content
    else:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the question."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
            ]
        )
        return response['choices'][0]['message']['content']

def main():
    # Create or update the search index
    create_search_index()

    # Process PDFs
    pdf_directory = "path/to/pdf/directory"
    for filename in os.listdir(pdf_directory):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(pdf_directory, filename)
            process_and_store_pdf(pdf_path)
    
    # Load SQL data into Cosmos DB
    load_sql_data_to_cosmos()
    
    # Process sensor data from Cosmos DB and store in Azure AI Search
    process_and_store_sensor_data()

    # Example search query
    query = "How to maintain the cooling system?"
    search_results = semantic_search(query)
    
    context = "\n".join([result['text'] for result in search_results])
    response = generate_response(query, context)
    
    print(f"Query: {query}")
    print(f"Generated Response: {response}")

if __name__ == "__main__":
    main()
