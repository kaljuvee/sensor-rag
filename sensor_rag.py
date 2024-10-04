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

# Load environment variables and initialize clients as before...

def create_search_index():
    # Same as before...

def process_pdf(pdf_path):
    # Same as before...

def upload_pdf_to_blob(pdf_path):
    # Same as before...

def get_embedding(text):
    # Same as before...

def store_document(id, text, embedding, metadata):
    # Store in Azure AI Search
    search_client.upload_documents([{
        "id": id,
        "text": text,
        "embedding": embedding,
        "metadata": str(metadata)
    }])

def process_and_store_pdf(pdf_path):
    # Same as before...

def get_sensor_relationship_data():
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD}')
    query = "SELECT * FROM SensorRelationships"  # Adjust this query as needed
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_sensor_realtime_data():
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD}')
    query = "SELECT * FROM SensorRealtimeData"  # Adjust this query as needed
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def load_sensor_data_to_cosmos():
    relationship_df = get_sensor_relationship_data()
    realtime_df = get_sensor_realtime_data()
    
    for _, row in relationship_df.iterrows():
        cosmos_container.upsert_item({
            "id": f"relationship_{row['sensor_id']}",
            "sensor_id": str(row['sensor_id']),
            "related_sensors": row['related_sensors'],
            "location": row['location'],
            "type": "relationship"
        })
    
    for _, row in realtime_df.iterrows():
        cosmos_container.upsert_item({
            "id": f"realtime_{row['sensor_id']}_{row['timestamp']}",
            "sensor_id": str(row['sensor_id']),
            "timestamp": str(row['timestamp']),
            "value": row['value'],
            "type": "realtime"
        })
    
    print(f"Loaded {len(relationship_df)} relationship records and {len(realtime_df)} realtime records into Cosmos DB")

def process_and_store_sensor_relationship_data():
    query = "SELECT * FROM c WHERE c.type = 'relationship'"
    items = list(cosmos_container.query_items(query=query, enable_cross_partition_query=True))
    
    for item in items:
        text = f"Sensor {item['sensor_id']} is related to sensors {item['related_sensors']} and is located at {item['location']}"
        embedding = get_embedding(text)
        store_document(
            id=f"sensor_relationship_{item['sensor_id']}",
            text=text,
            embedding=embedding,
            metadata={"type": "sensor_relationship", "sensor_id": item['sensor_id']}
        )

def get_latest_sensor_data(sensor_id):
    query = f"SELECT TOP 1 * FROM c WHERE c.type = 'realtime' AND c.sensor_id = '{sensor_id}' ORDER BY c._ts DESC"
    items = list(cosmos_container.query_items(query=query, enable_cross_partition_query=True))
    return items[0] if items else None

def semantic_search(query, top_k=5):
    # Same as before...

def generate_response(query, context, realtime_data=None):
    # Same as before...

def main():
    # Create or update the search index
    create_search_index()

    # Process PDFs
    pdf_directory = "path/to/pdf/directory"
    for filename in os.listdir(pdf_directory):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(pdf_directory, filename)
            process_and_store_pdf(pdf_path)
    
    # Load sensor data into Cosmos DB
    load_sensor_data_to_cosmos()
    
    # Process sensor relationship data and store in Azure AI Search
    process_and_store_sensor_relationship_data()

    # Example search query
    query = "What's the status of the cooling system?"
    search_results = semantic_search(query)
    
    context = "\n".join([result['text'] for result in search_results])
    
    # Get real-time data for relevant sensors
    realtime_data = []
    for result in search_results:
        if result['metadata']['type'] == 'sensor_relationship':
            sensor_id = result['metadata']['sensor_id']
            latest_data = get_latest_sensor_data(sensor_id)
            if latest_data:
                realtime_data.append(f"Sensor {sensor_id}: {latest_data['value']} at {latest_data['timestamp']}")
    
    realtime_context = "\n".join(realtime_data)
    
    response = generate_response(query, context, realtime_context)
    
    print(f"Query: {query}")
    print(f"Generated Response: {response}")

if __name__ == "__main__":
    main()
