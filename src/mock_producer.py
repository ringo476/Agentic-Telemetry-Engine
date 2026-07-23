from multiprocessing import shared_memory
import time
import struct
import random

TOTAL_SIZE = 1088  # 64-byte Control Block + (16 slots * 64 bytes)
MAX_SLOTS = 16

try:
    # FIX: Passed boolean and integer correctly, used TOTAL_SIZE variable
    shm = shared_memory.SharedMemory(name="telemetry_ring", create=True, size=TOTAL_SIZE)
    
    # FIX: Explicitly initialize the Head and Tail to 0 right after creation
    shm.buf[0:8] = struct.pack('ii', 0, 0)
    print("[Producer] Shared memory created and initialized.")
except:
    # FIX: Passed boolean correctly
    shm = shared_memory.SharedMemory(name="telemetry_ring", create=False)
    print("[Producer] Attached to existing shared memory.")

errors_to_simulate = [
    b"OOM_KILL: inference_engine limit reached",
    b"TCP_TIMEOUT: db_connection dropped",
    b"RING_BUFFER_OVERFLOW: rx_queue saturated"
]

try:
    for error in errors_to_simulate:  # FIX: Cleaned up variable loop name to 'error'
        # Simulating a small delay between telemetry updates
        time.sleep(random.randint(1, 3))
        
        # 1. Read the Control Block layout safely
        head, tail = struct.unpack('ii56x', bytes(shm.buf[:64]))
        
        # 2. Modulo Math: Determine the next slot
        next_head = (head + 1) % MAX_SLOTS
        
        # 3. Buffer Overflow Protection
        if next_head == tail:
            print(f"[Producer] WARNING: Ring buffer full! Dropping telemetry.")
            continue
        
        # 4. Calculate exact offset
        offset = 64 + (head * 64)
        
        # 5. Pack the string and write exactly to that offset
        packed_bytes = struct.pack('64s', error)
        shm.buf[offset : offset + 64] = packed_bytes
        
        # 6. Update ONLY the Head pointer in the Control Block (Bytes 0-3)
        shm.buf[0:4] = struct.pack('i', next_head)
        
        print(f"[Producer] INJECTED at Slot {head}: {error.decode()}")
        
except KeyboardInterrupt:
    print("\nShutting down simulator...")
finally:
    # 4. Free the memory so the host machine doesn't leak RAM
    shm.close()
    try:
        shm.unlink()
        print("[Producer] Shared memory unlinked successfully.")
    except FileNotFoundError:
        pass