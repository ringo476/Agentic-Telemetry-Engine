from multiprocessing import shared_memory
import time
import struct
import os
import json
import sqlalchemy
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("FATAL ERROR: DATABASE_URL is missing from the .env file.")
engine = sqlalchemy.create_engine(DB_URL)

print("[Daemon] Loading HuggingFace model into RAM...")
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

print("[Daemon] Booting AI Ingestion Pipeline...")

MAX_SLOTS = 16

try:
    shm = shared_memory.SharedMemory(name="telemetry_ring")
    print("[Daemon] Successfully attached to 'telemetry_ring' memory map.")
except FileNotFoundError:
    print("ERROR: Memory block not found. Start the producer first.")
    exit(1)

try:
    while True:
        # 1. Read Head (Bytes 0-3) and Tail (Bytes 4-7)
        head = struct.unpack('i', bytes(shm.buf[0:4]))[0]
        tail = struct.unpack('i', bytes(shm.buf[4:8]))[0]
        
        # 2. If Tail == Head, the buffer is empty. Do nothing.
        if tail != head:
            # 3. Calculate exact RAM byte offset for the current Tail slot
            offset = 64 + (tail * 64)
            
            # 4. Rip the raw bytes from that slot and unpack them into a string
            raw_bytes = bytes(shm.buf[offset : offset + 64])
            current_error = struct.unpack('64s', raw_bytes)[0].strip(b'\x00')
            error_text = current_error.decode()
            
            print(f"\n[Daemon] INTERCEPTED at Slot {tail}: {error_text}")
            
            # --- THE PGVECTOR AI PIPELINE ---
            print("         -> Generating 384-dimension vector via HuggingFace...")
            vector = str(embedding_model.embed_query(error_text))
            
            error_json = json.dumps({"raw_error": error_text, "source": "ring_buffer"})
            print("         -> Executing SQL INSERT into Postgres (resolution_notes=NULL)...")
            
            insert_sql = sqlalchemy.text(""" 
                INSERT INTO system_error_logs(error_details, resolution_notes, embedding)
                VALUES (:details, NULL, :vec)
            """)
            
            with engine.connect() as conn:
                conn.execute(insert_sql, {"details": error_json, "vec": vector})
                conn.commit()
            
            print("         -> AI Database successfully updated.")
            # --------------------------------
            
            # 5. Advance the Tail pointer to free the slot
            next_tail = (tail + 1) % MAX_SLOTS
            
            # FIXED: Write exactly 4 bytes exclusively to the Tail address (Bytes 4-7)
            # This completely avoids race conditions with the Producer.
            shm.buf[4:8] = struct.pack('i', next_tail)

        # Microsecond polling
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n[Daemon] Shutting down...")
finally:
    shm.close()