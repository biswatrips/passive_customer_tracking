import asyncio
import time
import sqlite3
import math
import pandas as pd
from bleak import BleakScanner
import serial_asyncio

# ==================== CONFIGURATION ====================
ZONE_ID = "bay_01"
DB_PATH = "retail_analytics.db"
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 256000
MIN_ENERGY_THRESHOLD = 20  # Ignore low-energy ghost reflections
# =======================================================

class ZoneNodeTracker:
    def __init__(self):
        self.ble_signals = []
        self.latest_mmwave_dist = 0.0
        self.latest_mmwave_presence = 0
        self.init_db()

    def init_db(self):
        """Initializes SQLite database with WAL mode for safe concurrent access and classification schema."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                presence_detected INTEGER NOT NULL,
                mmwave_distance REAL,
                ble_density INTEGER,
                avg_rssi REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bay_probabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_start REAL NOT NULL,
                window_end REAL NOT NULL,
                zone_id TEXT NOT NULL,
                derived_probability REAL NOT NULL,
                estimated_dwell_seconds REAL,
                engagement_type TEXT DEFAULT 'Browsing',
                passerby_density INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    async def scan_ble_passively(self):
        """Passively sniffs all Bluetooth advertisements to track ambient crowd density."""
        def detection_callback(device, advertisement_data):
            self.ble_signals.append({
                'rssi': advertisement_data.rssi,
                'time': time.time()
            })

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        print(f"[{ZONE_ID}] Passive BLE Scanner started...")
        
        try:
            while True:
                await asyncio.sleep(1.0)
                current_time = time.time()
                self.ble_signals = [s for s in self.ble_signals if current_time - s['time'] < 5.0]
        finally:
            await scanner.stop()

    def parse_ld2410_frame(self, frame):
        """Parses binary frames from the LD2410 radar."""
        if len(frame) < 20:
            return None
        if frame[:4] != b'\xf4\xf3\xf2\xf1' or frame[-4:] != b'\xf8\xf7\xf6\xf5':
            return None

        try:
            target_state = frame[8]
            mov_distance = int.from_bytes(frame[9:11], byteorder='little')
            mov_energy = frame[11]
            stat_distance = int.from_bytes(frame[12:14], byteorder='little')
            stat_energy = frame[14]
            
            return {
                "target_state": target_state,
                "moving_distance": mov_distance,
                "moving_energy": mov_energy,
                "stationary_distance": stat_distance,
                "stationary_energy": stat_energy
            }
        except Exception:
            return None

    async def poll_mmwave_serial(self):
        """Asynchronously reads and buffers binary frames from the HLK-LD2410C radar."""
        print(f"[{ZONE_ID}] Connecting to binary mmWave radar on {SERIAL_PORT}...")
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=SERIAL_PORT, baudrate=BAUD_RATE
            )
            buffer = bytearray()
            
            while True:
                data = await reader.read(1024)
                if data:
                    buffer.extend(data)
                    
                    while True:
                        start_idx = buffer.find(b'\xf4\xf3\xf2\xf1')
                        if start_idx == -1:
                            break
                        
                        end_idx = buffer.find(b'\xf8\xf7\xf6\xf5', start_idx)
                        if end_idx == -1:
                            break
                        
                        frame = buffer[start_idx:end_idx + 4]
                        buffer = buffer[end_idx + 4:]
                        
                        parsed = self.parse_ld2410_frame(frame)
                        if parsed:
                            has_movement = parsed["moving_energy"] > MIN_ENERGY_THRESHOLD
                            has_stationary = parsed["stationary_energy"] > MIN_ENERGY_THRESHOLD
                            
                            if not has_movement and not has_stationary:
                                self.latest_mmwave_presence = 0
                                self.latest_mmwave_dist = 0.0
                            else:
                                self.latest_mmwave_presence = 1
                                mov_d = parsed["moving_distance"]
                                stat_d = parsed["stationary_distance"]
                                
                                if has_movement and has_stationary:
                                    self.latest_mmwave_dist = (mov_d + stat_d) / 2.0
                                elif has_movement:
                                    self.latest_mmwave_dist = float(mov_d)
                                else:
                                    self.latest_mmwave_dist = float(stat_d)
                                    
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"[{ZONE_ID}] Binary serial warning: {e}. Running without radar hardware.")
            while True:
                await asyncio.sleep(1.0)

    async def telemetry_logger_loop(self):
        """Periodic loop capturing live sensor states and logging raw data to SQLite every 2 seconds."""
        while True:
            await asyncio.sleep(2.0)
            
            current_time = time.time()
            mmwave_presence = self.latest_mmwave_presence
            mmwave_dist = self.latest_mmwave_dist

            # Only capture BLE metrics if mmWave radar detects someone present (gated check)
            if mmwave_presence == 1:
                ble_count = len(self.ble_signals)
                avg_rssi = sum(s['rssi'] for s in self.ble_signals) / max(1, ble_count) if ble_count > 0 else -99.0
            else:
                ble_count = 0
                avg_rssi = -99.0

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telemetry_logs (zone_id, timestamp, presence_detected, mmwave_distance, ble_density, avg_rssi)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ZONE_ID, current_time, mmwave_presence, mmwave_dist, ble_count, avg_rssi))
            conn.commit()
            conn.close()

    async def periodic_probability_batch_loop(self, window_minutes=2):
        """Background worker evaluating probability, dwell times, and behavioral intent patterns."""
        while True:
            await asyncio.sleep(window_minutes * 60)
            
            now = time.time()
            window_start = now - (window_minutes * 60)
            
            conn = sqlite3.connect(DB_PATH)
            query = f"""
                SELECT zone_id, timestamp, presence_detected, mmwave_distance, ble_density, avg_rssi
                FROM telemetry_logs
                WHERE timestamp >= {window_start} AND zone_id = '{ZONE_ID}'
            """
            df = pd.read_sql(query, conn)
            
            if df.empty:
                conn.close()
                continue

            active_df = df[df['presence_detected'] == 1]
            estimated_dwell = df['presence_detected'].sum() * 2.0 

            if not active_df.empty:
                valid_distances = active_df[active_df['mmwave_distance'] > 0.0]['mmwave_distance']
                avg_distance = valid_distances.mean() if not valid_distances.empty else 999.0
                avg_density = active_df['ble_density'].mean()
                distance_variance = valid_distances.std() if len(valid_distances) > 1 else 0.0

                # --- BEHAVIORAL INTENT CLASSIFICATION ---
                if avg_distance > 90.0:
                    engagement_type = "Low-Intent Traffic (Passerby)"
                    normalized_prob = 0.20
                elif avg_density > 35.0 and distance_variance > 20.0:
                    engagement_type = "Crowded Engagement (High Traffic)"
                    normalized_prob = 0.85
                else:
                    engagement_type = "Focused Single Browsing"
                    normalized_prob = 0.75
            else:
                engagement_type = "Vacant"
                normalized_prob = 0.0
                avg_density = 0

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bay_probabilities (window_start, window_end, zone_id, derived_probability, estimated_dwell_seconds, engagement_type, passerby_density)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (window_start, now, ZONE_ID, normalized_prob, estimated_dwell, engagement_type, int(avg_density)))
            conn.commit()
            conn.close()
            
            print(f"[{ZONE_ID}] Batch Analyzed | Type: {engagement_type} | Prob: {normalized_prob:.2f} | Est Dwell: {estimated_dwell}s")

    async def run(self):
        """Runs all asynchronous workers concurrently."""
        await asyncio.gather(
            self.scan_ble_passively(),
            self.poll_mmwave_serial(),
            self.telemetry_logger_loop(),
            self.periodic_probability_batch_loop(window_minutes=2)
        )

if __name__ == "__main__":
    node = ZoneNodeTracker()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        print(f"\n[{ZONE_ID}] Tracker stopped safely.")
