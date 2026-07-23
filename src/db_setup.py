import sqlalchemy
import json
from langchain_huggingface import HuggingFaceEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

print("Loading HuggingFace model into RAM...")
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

engine = sqlalchemy.create_engine(DB_URL)

setup_sql="""
-- 1. Enable the vector math engine inside Postgres
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS node_telemetry_metrics;
DROP TABLE IF EXISTS active_tcp_sessions;
DROP TABLE IF EXISTS system_error_logs;
-- 2. The Hardware Health Table
CREATE TABLE node_telemetry_metrics(
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    node_id VARCHAR(50),
    rx_pps INTEGER,
    tx_pps INTEGER,
    ring_buffer_utlization FLOAT,
    dropped_packets INTEGER
);

-- 3. The Protocol State Table
CREATE TABLE active_tcp_sessions (
    session_id VARCHAR(50),
    source_ip VARCHAR(50),
    dest_ip VARCHAR(50),
    protocol VARCHAR(10),
    state VARCHAR(20),
    bytes_transferred INTEGER
);

-- 4. The AI Vector / JSONB Table (For RAG)
CREATE TABLE system_error_logs(
    log_id SERIAL PRIMARY KEY,
    error_details JSONB,
    resolution_notes TEXT,embedding VECTOR(384)
)
"""

print("Creating Unified AI and Telemetry tables...")
with engine.connect() as conn:
    conn.execute(sqlalchemy.text(setup_sql))
    conn.commit()

    print("Injecting Network Telemetry Data...")
    conn.execute(sqlalchemy.text(""" 
        INSERT INTO active_tcp_sessions(session_id,source_ip,dest_ip,protocol,state, bytes_transferred)
        VALUES('uuid-9999', '192.168.1.100', '10.0.0.5', 'TCP', 'FIN_WAIT', 8402)                        
    """ ))
    conn.commit()

    print("Generating and Injecting AI Vector Data...")
    
    # We define the raw English text for the errors
    error_1_text = "OOM_KILL inference engine line 42"
    error_2_text = "RING_BUFFER_OVERFLOW dpdk_worker line 104"

    vector_1=str(embedding_model.embed_query(error_1_text))
    vector_2=str(embedding_model.embed_query(error_2_text))

    insert_vector_sql=sqlalchemy.text(""" 
        INSERT INTO system_error_logs(error_details,resolution_notes,embedding)
        VALUES
        ('{"error_code":"OOM_KILL","module":"interference_engine"}','Increased container memory limit to 16GB.',:v1),
        ('{"error_code": "RING_BUFFER_OVERFLOW", "module": "dpdk_worker"}', 'Rebalanced RX queues across multiple cores.', :v2)
    """)

    conn.execute(insert_vector_sql,{"v1":vector_1,"v2":vector_2})
    conn.commit()

print("Unified database seeded successfully with 384-dimension vectors.")    
