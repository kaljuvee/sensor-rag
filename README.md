# RAG Application with Factory Manuals and Sensor Data

This Retrieval-Augmented Generation (RAG) application processes and integrates three types of data:

1. PDF Documents: Factory operating manuals stored as PDFs.
2. Sensor Relationship Data: Information about how sensors are related and their locations and their dependencies / relationships to other sensors.
3. Sensor Real-time Data: Current readings from sensors.

## Data Processing and Storage

- PDF documents are processed, embedded, and indexed in Azure AI Search.
- Sensor relationship data is fetched from SQL, stored in Cosmos DB, embedded, and indexed in Azure AI Search.
- Sensor real-time data is fetched from SQL and stored in Cosmos DB but not indexed or embedded.

## Query Process

1. When a query is received, the application performs a semantic search on the indexed data (PDFs and sensor relationships) in Azure AI Search.
2. For relevant sensors found in the search results, the latest real-time data is fetched from Cosmos DB.
3. The search results and real-time data are combined to generate a response using OpenAI or Azure OpenAI.

## Data Storage and Indexing

Our application uses a combination of Azure services for efficient data storage and retrieval:

1. Azure Blob Storage: Stores the raw PDF files.
2. Azure Cosmos DB: 
   - Stores sensor relationship data
   - Stores real-time sensor data (not indexed or embedded)
3. Azure AI Search: 
   - Indexes and stores PDF content along with their embeddings
   - Indexes and stores sensor relationship data along with their embeddings
   - Provides efficient vector search capabilities for semantic queries

This architecture allows us to leverage the strengths of each service:
- Blob Storage for cost-effective storage of large files
- Cosmos DB for flexible, scalable storage of structured and semi-structured data, including frequently updating real-time data
- Azure AI Search for powerful indexing and vector search capabilities on more static data (PDFs and sensor relationships)

## Application Flow

Below is a sequence diagram illustrating the main flow of the RAG application:

![RAG Application Sequence Diagram](sequence-diagram.PNG)

This diagram shows the interactions between various components of the system, including the user, application, PDF processor, Azure services (Blob Storage, Cosmos DB, AI Search), SQL Database, and OpenAI.

## Key Features

- Separate processing for PDF documents, sensor relationship data, and sensor real-time data.
- Use of Cosmos DB for efficient storage and retrieval of both relationship and real-time sensor data.
- Semantic search capabilities for PDF content and sensor relationship data using Azure AI Search.
- Integration of real-time sensor data in query responses without indexing this frequently changing data.
- Flexible use of either OpenAI API or Azure OpenAI Service for embeddings and response generation.

