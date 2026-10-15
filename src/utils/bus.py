"""
File: screeni/utils/bus.py
Purpose: Event bus and database for emitting and storing signals
"""

import json
import logging
import queue
import sqlite3
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SignalDatabase:
    """Manages SQLite database for signal analytics."""
    
    def __init__(self, db_path: str = 'user_data/signals_analytics.sqlite'):
        """Initialize database connection and ensure schema."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._init_tables()
    
    @property
    def conn(self):
        """Get active database connection with safety check."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _init_tables(self):
        """Create all tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence REAL,
                score REAL,
                indicators TEXT,
                ml_prediction TEXT,
                patterns_detected TEXT,
                metadata TEXT
            )
        ''')
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL,
                entry_time TEXT,
                exit_price REAL,
                exit_time TEXT,
                quantity INTEGER,
                pnl REAL,
                pnl_percent REAL,
                exit_reason TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        ''')
        
        # Patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_occurrences (
                id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern_name TEXT NOT NULL,
                confidence REAL,
                timeframe TEXT,
                metadata TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        ''')
        
        # Models table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_versions (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                accuracy REAL,
                precision REAL,
                recall REAL,
                f1_score REAL,
                trained_on TEXT,
                metadata TEXT
            )
        ''')
        
        self.conn.commit()
    
    def save_signal(self, signal_data: dict[str, Any]) -> str:
        """Store a new signal with complete metadata."""
        signal_id = signal_data.get('id', str(uuid.uuid4()))
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO signals 
            (id, symbol, timestamp, signal_type, confidence, score, indicators, 
             ml_prediction, patterns_detected, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_id,
            signal_data.get('symbol', ''),
            signal_data.get('timestamp', datetime.now().isoformat()),
            signal_data.get('signal_type', ''),
            signal_data.get('confidence', 0.0),
            signal_data.get('score', 0.0),
            json.dumps(signal_data.get('indicators', {})),
            json.dumps(signal_data.get('ml_prediction', {})),
            json.dumps(signal_data.get('patterns_detected', [])),
            json.dumps(signal_data.get('metadata', {}))
        ))
        self.conn.commit()
        return signal_id
    
    def save_trade(self, trade_data: dict[str, Any]) -> str:
        """Link an executed trade record to an existing signal."""
        trade_id = trade_data.get('id', str(uuid.uuid4()))
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO trades 
            (id, signal_id, symbol, entry_price, entry_time, quantity, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id,
            trade_data.get('signal_id', ''),
            trade_data.get('symbol', ''),
            trade_data.get('entry_price', 0.0),
            trade_data.get('entry_time', datetime.now().isoformat()),
            trade_data.get('quantity', 0),
            json.dumps(trade_data.get('metadata', {}))
        ))
        self.conn.commit()
        return trade_id
    
    def update_trade_outcome(self, trade_id: str, outcome_data: dict[str, Any]) -> None:
        """Update trade with exit info and calculate realized P&L."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE trades 
            SET exit_price = ?, exit_time = ?, pnl = ?, pnl_percent = ?, exit_reason = ?
            WHERE id = ?
        ''', (
            outcome_data.get('exit_price', 0.0),
            outcome_data.get('exit_time', datetime.now().isoformat()),
            outcome_data.get('pnl', 0.0),
            outcome_data.get('pnl_percent', 0.0),
            outcome_data.get('exit_reason', ''),
            trade_id
        ))
        self.conn.commit()
    
    def save_pattern(self, pattern_data: dict[str, Any]) -> str:
        """Store individual pattern occurrence from a signal."""
        pattern_id = str(uuid.uuid4())
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO pattern_occurrences 
            (id, signal_id, pattern_type, pattern_name, confidence, timeframe, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            pattern_id,
            pattern_data.get('signal_id', ''),
            pattern_data.get('pattern_type', ''),
            pattern_data.get('pattern_name', ''),
            pattern_data.get('confidence', 0.0),
            pattern_data.get('timeframe', '1d'),
            json.dumps(pattern_data.get('metadata', {}))
        ))
        self.conn.commit()
        return pattern_id
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SignalBus:
    """
    Singleton event bus for emitting signals from scanner to database.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._queue = queue.Queue()
        self._listeners = []
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        self._stats = {"events_processed": 0, "events_queued": 0}
        self._initialized = True
        self._db = SignalDatabase()
    
    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event to the bus queue for async processing."""
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self._queue.put(event)
        self._stats["events_queued"] += 1
    
    def register_listener(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Register a listener for all events passing through the bus."""
        self._listeners.append(callback)
    
    def unregister_listener(self, callback: Callable) -> None:
        """Remove a previously registered listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _worker(self):
        """Background worker to process events from the queue."""
        while self._running:
            try:
                event = self._queue.get(timeout=1)
                self._process_event(event)
                self._stats["events_processed"] += 1
            except queue.Empty:
                continue
    
    def _process_event(self, event: dict[str, Any]):
        """Process a single event by saving to DB and notifying listeners."""
        # Save to database based on event type
        if event["type"] == "signal_generated":
            self._db.save_signal(event["data"])
        elif event["type"] == "trade_executed":
            self._db.save_trade(event["data"])
        elif event["type"] == "pattern_detected":
            self._db.save_pattern(event["data"])
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event["type"], event["data"])
            except Exception:
                logger.exception("Error in event listener")
    
    def stop(self):
        """Stop the background worker thread."""
        self._running = False
        self._worker_thread.join(timeout=5)
    
    def get_stats(self) -> dict[str, Any]:
        """Get aggregated statistics about bus performance and state."""
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "listener_count": len(self._listeners)
        }


class SignalEmitter:
    """Mixin class for scanner components to emit signals asynchronously."""
    
    def __init__(self):
        """Initialize the emitter by acquiring the SignalBus singleton."""
        self._bus = SignalBus()
    
    def emit_signal(self, signal_data: dict[str, Any]) -> None:
        """Emit a signal to the analytics system with metadata injection."""
        self._bus.emit("signal_generated", signal_data)
    
    def emit_trade(self, trade_data: dict[str, Any]) -> None:
        """Emit a trade execution event for tracking and performance analysis."""
        self._bus.emit("trade_executed", trade_data)
