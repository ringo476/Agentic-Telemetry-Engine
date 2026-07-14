from mcp.server.fastmcp import FastMCP
import sqlalchemy
import json
from langchain_huggingface import HuggingFaceEmbeddings

# ==========================================
# 1. INITIALIZE SERVER & DATABASE
# ==========================================
# We name the server so the client knows what it's connecting to
mcp = FastMCP("TelemetryDB_Server")

embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# The connection string. Format: postgresql://user:password@host:port/database_name
# 'postgres' is the default database created upon installation.
DB_URL = "postgresql://postgres:secret@localhost:5432/postgres"
engine = sqlalchemy.create_engine(DB_URL)

# ==========================================
# 2. DEFINE THE TOOLS
# ==========================================

@mcp.tool()
def get_database_schema() -> str:
    """
    Always call this FIRST before writing any SQL queries. 
    It returns the exact table names, columns, and data types in the database.
    """
    # We pass the exact schema we discussed directly to the LLM so it never guesses.
    schema = """
    Table 1: node_telemetry_metrics
    - timestamp (TIMESTAMP)
    - node_id (VARCHAR): e.g., 'Node_A', 'Node_B'
    - rx_pps (INTEGER): Packets per second received
    - tx_pps (INTEGER): Packets per second transmitted
    - ring_buffer_utilization (FLOAT): Percentage buffer filled (0.0 to 100.0)
    - dropped_packets (INTEGER): Number of packets dropped at the NIC
    
    Table 2: active_tcp_sessions
    - session_id (VARCHAR)
    - source_ip (VARCHAR)
    - dest_ip (VARCHAR)
    - protocol (VARCHAR): e.g., 'TCP', 'UDP'
    - state (VARCHAR): e.g., 'ESTABLISHED', 'FIN_WAIT', 'TIME_WAIT'
    - bytes_transferred (INTEGER)

    Table 3: system_error_logs (AI Vector RAG Memory)
    - log_id (SERIAL)
    - error_details (JSONB)
    - resolution_notes (TEXT)
    - embedding (VECTOR)
    """
    return schema


@mcp.tool()
def execute_read_only_sql(query: str) -> str:
    """
    Executes a raw SQL SELECT query against the telemetry database and returns the results.
    Provide the exact SQL query as the argument.
    """
    # Bare-metal security: Block the AI from running DROP, DELETE, or UPDATE.
    if not query.strip().upper().startswith("SELECT"):
        return "ERROR: Security block. You are only allowed to run SELECT queries."
    try:
        with engine.connect() as connection:
            result=connection.execute(sqlalchemy.text(query))
            rows = []                               # 1. Create an empty array
            all_data = result.fetchall()
            for row in all_data:
                mapped_row=row._mapping
                dictionary_row=dict(mapped_row)
                rows.append(dictionary_row)
            if rows:
                return json.dumps(rows, default=str, indent=2)
            else:
                return "0 rows returned."
    except Exception as e:
        # If the AI writes bad SQL, we catch the Postgres crash and return the exact C-level error
        # back to the AI so it can fix its mistake and try again.
        return f"SQL Error: {str(e)}"
    

@mcp.tool()
def extract_json_log_keys(module_name:str)->str:
    """
    Extracts specific keys from the JSONB error logs for a given module.
    """
    query=f"""
        SELECT error_details->>'error_code' AS error_code,resolution_notes
        FROM system_error_logs
        WHERE error_details->>'module'='{module_name}';
    """
    try:
        with engine.connect() as connection:
            result=connection.execute(sqlalchemy.text(query))
            rows=[dict(row._mapping) for row in result.fetchall()]
            if rows:
                return json.dumps(rows,default=str,indent=2)
            else:
                return "No logs found."
    except Exception as e:
        return f"SQL Error: {str(e)}"

@mcp.tool()
def semantic_search_similar_errors(search_text: str) -> str:
    """
    Searches the database for past errors similar to the provided text.
    Pass the raw English text of the error (e.g., 'buffer overflow in dpdk').
    """
    try:
        vector_array=embedding_model.embed_query(search_text)
        vector_string=str(vector_array)
        query=f"""
            SELECT error_details,resolution_notes
            FROM system_error_logs
            ORDER BY embedding <-> '{vector_string}'
            LIMIT 2;
        """
        with engine.connect() as connection:
            result=connection.execute(sqlalchemy.text(query))
            rows=[dict(row._mapping) for row in result.fetchall()]
            if rows:
                return json.dumps(rows,default=str,indent=2)
            else:
                return "No matches."
    except Exception as e:
        return f"Vector Search Error: {str(e)}"
# ==========================================
# 3. START THE DAEMON
# ==========================================
if __name__ == "__main__":
    print("[MCP Server] Initializing on STDIO transport...")
    mcp.run()