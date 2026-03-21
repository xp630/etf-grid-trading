"""
持仓追踪器 - 管理当前持仓和交易记录
"""
import sqlite3
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    level_index: int
    buy_date: str


class PositionTracker:
    """持仓追踪器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity INTEGER,
                avg_price REAL,
                level_index INTEGER,
                buy_date TEXT
            )
        ''')

        # 交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                action TEXT,
                price REAL,
                quantity INTEGER,
                level_index INTEGER,
                timestamp TEXT,
                profit REAL
            )
        ''')

        conn.commit()
        conn.close()

    def record_buy(self, symbol: str, price: float, quantity: int, level_index: int):
        """记录买入"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        # 检查是否已有持仓
        cursor.execute('SELECT quantity, avg_price FROM positions WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()

        if row:
            # 更新持仓
            old_qty, old_avg = row
            new_qty = old_qty + quantity
            new_avg = (old_qty * old_avg + quantity * price) / new_qty

            cursor.execute('''
                UPDATE positions
                SET quantity = ?, avg_price = ?, level_index = ?
                WHERE symbol = ?
            ''', (new_qty, new_avg, level_index, symbol))
        else:
            # 新增持仓
            cursor.execute('''
                INSERT INTO positions (symbol, quantity, avg_price, level_index, buy_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, quantity, price, level_index, timestamp.split('T')[0]))

        # 记录交易
        cursor.execute('''
            INSERT INTO trades (symbol, action, price, quantity, level_index, timestamp, profit)
            VALUES (?, 'buy', ?, ?, ?, ?, NULL)
        ''', (symbol, price, quantity, level_index, timestamp))

        conn.commit()
        conn.close()

    def record_sell(self, symbol: str, price: float, quantity: int, level_index: int):
        """记录卖出"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        # 检查持仓
        cursor.execute('SELECT quantity, avg_price FROM positions WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise ValueError(f"No position to sell for {symbol}")

        current_qty, avg_price = row
        if current_qty < quantity:
            raise ValueError(f"Insufficient quantity: have {current_qty}, trying to sell {quantity}")

        # 计算盈利
        profit = (price - avg_price) * quantity

        if current_qty == quantity:
            # 全部卖出
            cursor.execute('DELETE FROM positions WHERE symbol = ?', (symbol,))
        else:
            # 部分卖出
            cursor.execute('''
                UPDATE positions
                SET quantity = quantity - ?
                WHERE symbol = ?
            ''', (quantity, symbol))

        # 记录交易
        cursor.execute('''
            INSERT INTO trades (symbol, action, price, quantity, level_index, timestamp, profit)
            VALUES (?, 'sell', ?, ?, ?, ?, ?)
        ''', (symbol, price, quantity, level_index, timestamp, profit))

        conn.commit()
        conn.close()

    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT symbol, quantity, avg_price, level_index, buy_date FROM positions')
        rows = cursor.fetchall()
        conn.close()

        return {
            row[0]: Position(
                symbol=row[0],
                quantity=row[1],
                avg_price=row[2],
                level_index=row[3],
                buy_date=row[4]
            )
            for row in rows
        }

    def get_total_value(self, current_price: float) -> float:
        """计算持仓总市值"""
        positions = self.get_all_positions()
        return sum(p.quantity * current_price for p in positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定持仓"""
        positions = self.get_all_positions()
        return positions.get(symbol)

    def is_level_holding(self, level_index: int) -> bool:
        """检查指定档位是否有持仓"""
        positions = self.get_all_positions()
        return any(p.level_index == level_index for p in positions.values())

    def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """获取交易记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if symbol:
            cursor.execute('''
                SELECT symbol, action, price, quantity, level_index, timestamp, profit
                FROM trades WHERE symbol = ?
                ORDER BY timestamp ASC LIMIT ?
            ''', (symbol, limit))
        else:
            cursor.execute('''
                SELECT symbol, action, price, quantity, level_index, timestamp, profit
                FROM trades
                ORDER BY timestamp ASC LIMIT ?
            ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'symbol': row[0],
                'action': row[1],
                'price': row[2],
                'quantity': row[3],
                'level_index': row[4],
                'timestamp': row[5],
                'profit': row[6]
            }
            for row in rows
        ]

    def get_daily_pnl(self) -> float:
        """计算当日盈亏"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT SUM(CASE
                WHEN action = 'buy' THEN -price * quantity
                WHEN action = 'sell' THEN price * quantity
            END)
            FROM trades
            WHERE timestamp LIKE ?
        ''', (f'{today}%',))

        result = cursor.fetchone()[0]
        conn.close()

        return result if result else 0.0