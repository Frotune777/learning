"""Performance tracking for Screeni-py."""

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class PerformanceTracker:
    """Tracks performance metrics for scans, signals, and trades."""
    
    def __init__(self, db_path: str = 'user_data/performance.db'):
        """Initialize performance tracker with database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._init_database()
    
    @property
    def conn(self):
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _init_database(self):
        """Initialize database tables."""
        cursor = self.conn.cursor()
        
        # Scans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                stocks_screened INTEGER,
                signals_generated INTEGER,
                duration_seconds REAL,
                notes TEXT
            )
        ''')
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT,
                entry_price REAL,
                confidence REAL,
                score REAL,
                metadata TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            )
        ''')
        
        # Outcomes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                exit_price REAL,
                exit_time TEXT,
                exit_reason TEXT,
                pnl REAL,
                pnl_percent REAL,
                holding_period_hours REAL,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        ''')
        
        self.conn.commit()
    
    def log_scan(self, stocks_screened: int, signals_generated: int, 
                 duration_seconds: float = 0, notes: str = '') -> int:
        """Log a new screening run."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO scans (timestamp, stocks_screened, signals_generated, 
                              duration_seconds, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            datetime.datetime.now().isoformat(),
            stocks_screened,
            signals_generated,
            duration_seconds,
            notes
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def log_signal(self, scan_id: int, symbol: str, entry_price: float,
                   signal_data: Dict[str, Any]) -> int:
        """Log a screening signal."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO signals (scan_id, timestamp, symbol, signal_type,
                               entry_price, confidence, score, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id,
            datetime.datetime.now().isoformat(),
            symbol,
            signal_data.get('signal_type', ''),
            entry_price,
            signal_data.get('confidence', 0.0),
            signal_data.get('score', 0.0),
            json.dumps(signal_data)
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def log_outcome(self, signal_id: int, exit_price: float, 
                    exit_reason: str, entry_price: float = None) -> None:
        """Log the outcome of a signal."""
        # If entry_price not provided, fetch it from signals table
        if entry_price is None:
            cursor = self.conn.cursor()
            cursor.execute('SELECT entry_price FROM signals WHERE id = ?', (signal_id,))
            row = cursor.fetchone()
            if row:
                entry_price = row['entry_price']
            else:
                entry_price = 0
        
        # Calculate P&L
        pnl = exit_price - entry_price
        pnl_percent = (pnl / entry_price * 100) if entry_price else 0
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO outcomes (signal_id, exit_price, exit_time, exit_reason,
                                pnl, pnl_percent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            signal_id,
            exit_price,
            datetime.datetime.now().isoformat(),
            exit_reason,
            pnl,
            pnl_percent
        ))
        self.conn.commit()
    
    def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get performance statistics for last N days."""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        
        cursor = self.conn.cursor()
        
        # Total scans
        cursor.execute('SELECT COUNT(*) FROM scans WHERE timestamp > ?', (cutoff,))
        total_scans = cursor.fetchone()[0]
        
        # Total signals
        cursor.execute('''
            SELECT COUNT(*) FROM signals s
            JOIN scans sc ON s.scan_id = sc.id
            WHERE sc.timestamp > ?
        ''', (cutoff,))
        total_signals = cursor.fetchone()[0]
        
        # Win rate
        cursor.execute('''
            SELECT COUNT(*) FROM outcomes o
            JOIN signals s ON o.signal_id = s.id
            JOIN scans sc ON s.scan_id = sc.id
            WHERE sc.timestamp > ? AND o.pnl > 0
        ''', (cutoff,))
        wins = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM outcomes o
            JOIN signals s ON o.signal_id = s.id
            JOIN scans sc ON s.scan_id = sc.id
            WHERE sc.timestamp > ?
        ''', (cutoff,))
        total_outcomes = cursor.fetchone()[0]
        
        win_rate = (wins / total_outcomes * 100) if total_outcomes > 0 else 0
        
        # Average P&L
        cursor.execute('''
            SELECT AVG(o.pnl_percent) FROM outcomes o
            JOIN signals s ON o.signal_id = s.id
            JOIN scans sc ON s.scan_id = sc.id
            WHERE sc.timestamp > ?
        ''', (cutoff,))
        avg_pnl = cursor.fetchone()[0] or 0
        
        return {
            'period_days': days,
            'total_scans': total_scans,
            'total_signals': total_signals,
            'total_outcomes': total_outcomes,
            'wins': wins,
            'win_rate': round(win_rate, 2),
            'avg_pnl_percent': round(avg_pnl, 2)
        }
    
    def get_recent_signals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent signals with outcomes."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.*, o.exit_price, o.exit_time, o.exit_reason, o.pnl, o.pnl_percent
            FROM signals s
            LEFT JOIN outcomes o ON s.id = o.signal_id
            ORDER BY s.timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        
        return results
    
    def export_to_excel(self, filename: str = None) -> str:
        """Export performance data to Excel (placeholder)."""
        if filename is None:
            filename = f"performance_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # This is a placeholder - actual Excel export would require pandas/openpyxl
        print(f"📊 Performance data would be exported to {filename}")
        return filename
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
