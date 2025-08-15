"""
数据访问层 - Repository模式实现
提供数据库操作的抽象接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, TypeVar, Generic
from datetime import datetime, date
from sqlalchemy import select, update, delete, and_, or_, desc, asc, func
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from quant_framework.database.base import Base, get_async_session, get_sync_session
from quant_framework.database.models import (
    User, Strategy, BacktestResult, TradeRecord, PositionRecord, 
    SecurityInfo, DataSource, SystemLog
)
from quant_framework.core.constants import StrategyStatus, BacktestStatus
from quant_framework.utils.logger import LoggerMixin

# 泛型类型变量
T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T], LoggerMixin, ABC):
    """基础仓库类"""
    
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class
    
    async def create(self, session: AsyncSession, **kwargs) -> T:
        """创建记录"""
        try:
            instance = self.model_class(**kwargs)
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance
        except Exception as e:
            self.log_error(e, {"method": "create", "model": self.model_class.__name__})
            raise
    
    async def get_by_id(self, session: AsyncSession, id: int) -> Optional[T]:
        """根据ID获取记录"""
        try:
            result = await session.execute(
                select(self.model_class).where(self.model_class.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.log_error(e, {"method": "get_by_id", "model": self.model_class.__name__, "id": id})
            raise
    
    async def get_all(
        self, 
        session: AsyncSession, 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """获取所有记录"""
        try:
            query = select(self.model_class)
            
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_all", "model": self.model_class.__name__})
            raise
    
    async def update(self, session: AsyncSession, id: int, **kwargs) -> Optional[T]:
        """更新记录"""
        try:
            # 添加更新时间
            if hasattr(self.model_class, 'updated_at'):
                kwargs['updated_at'] = datetime.now()
            
            await session.execute(
                update(self.model_class)
                .where(self.model_class.id == id)
                .values(**kwargs)
            )
            
            return await self.get_by_id(session, id)
        except Exception as e:
            self.log_error(e, {"method": "update", "model": self.model_class.__name__, "id": id})
            raise
    
    async def delete(self, session: AsyncSession, id: int) -> bool:
        """删除记录"""
        try:
            result = await session.execute(
                delete(self.model_class).where(self.model_class.id == id)
            )
            return result.rowcount > 0
        except Exception as e:
            self.log_error(e, {"method": "delete", "model": self.model_class.__name__, "id": id})
            raise
    
    async def count(self, session: AsyncSession, **filters) -> int:
        """统计记录数"""
        try:
            query = select(func.count(self.model_class.id))
            
            # 添加过滤条件
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.where(getattr(self.model_class, key) == value)
            
            result = await session.execute(query)
            return result.scalar()
        except Exception as e:
            self.log_error(e, {"method": "count", "model": self.model_class.__name__})
            raise


class UserRepository(BaseRepository[User]):
    """用户仓库"""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_by_username(self, session: AsyncSession, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        try:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.log_error(e, {"method": "get_by_username", "username": username})
            raise
    
    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        try:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.log_error(e, {"method": "get_by_email", "email": email})
            raise
    
    async def get_active_users(self, session: AsyncSession) -> List[User]:
        """获取活跃用户"""
        try:
            result = await session.execute(
                select(User).where(User.is_active == True)
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_active_users"})
            raise


class StrategyRepository(BaseRepository[Strategy]):
    """策略仓库"""
    
    def __init__(self):
        super().__init__(Strategy)
    
    async def get_by_author(
        self, 
        session: AsyncSession, 
        author_id: int,
        status: Optional[StrategyStatus] = None
    ) -> List[Strategy]:
        """根据作者获取策略"""
        try:
            query = select(Strategy).where(Strategy.author_id == author_id)
            
            if status:
                query = query.where(Strategy.status == status.value)
            
            query = query.order_by(desc(Strategy.updated_at))
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_author", "author_id": author_id})
            raise
    
    async def get_by_status(self, session: AsyncSession, status: StrategyStatus) -> List[Strategy]:
        """根据状态获取策略"""
        try:
            result = await session.execute(
                select(Strategy)
                .where(Strategy.status == status.value)
                .order_by(desc(Strategy.updated_at))
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_status", "status": status.value})
            raise
    
    async def search_by_name(self, session: AsyncSession, name_pattern: str) -> List[Strategy]:
        """根据名称搜索策略"""
        try:
            result = await session.execute(
                select(Strategy)
                .where(Strategy.name.ilike(f"%{name_pattern}%"))
                .order_by(desc(Strategy.updated_at))
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "search_by_name", "pattern": name_pattern})
            raise
    
    async def update_status(
        self, 
        session: AsyncSession, 
        strategy_id: int, 
        status: StrategyStatus
    ) -> Optional[Strategy]:
        """更新策略状态"""
        return await self.update(session, strategy_id, status=status.value)


class BacktestResultRepository(BaseRepository[BacktestResult]):
    """回测结果仓库"""
    
    def __init__(self):
        super().__init__(BacktestResult)
    
    async def get_by_strategy(
        self, 
        session: AsyncSession, 
        strategy_id: int,
        status: Optional[BacktestStatus] = None
    ) -> List[BacktestResult]:
        """根据策略获取回测结果"""
        try:
            query = select(BacktestResult).where(BacktestResult.strategy_id == strategy_id)
            
            if status:
                query = query.where(BacktestResult.status == status.value)
            
            query = query.order_by(desc(BacktestResult.created_at))
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_strategy", "strategy_id": strategy_id})
            raise
    
    async def get_by_user(
        self, 
        session: AsyncSession, 
        user_id: int,
        limit: Optional[int] = None
    ) -> List[BacktestResult]:
        """根据用户获取回测结果"""
        try:
            query = (
                select(BacktestResult)
                .where(BacktestResult.user_id == user_id)
                .order_by(desc(BacktestResult.created_at))
            )
            
            if limit:
                query = query.limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_user", "user_id": user_id})
            raise
    
    async def get_completed_results(
        self, 
        session: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[BacktestResult]:
        """获取已完成的回测结果"""
        try:
            query = select(BacktestResult).where(
                BacktestResult.status == BacktestStatus.COMPLETED.value
            )
            
            if start_date:
                query = query.where(BacktestResult.start_date >= start_date)
            if end_date:
                query = query.where(BacktestResult.end_date <= end_date)
            
            query = query.order_by(desc(BacktestResult.completed_at))
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_completed_results"})
            raise
    
    async def update_status(
        self, 
        session: AsyncSession, 
        backtest_id: int, 
        status: BacktestStatus,
        **kwargs
    ) -> Optional[BacktestResult]:
        """更新回测状态"""
        update_data = {"status": status.value}
        
        # 根据状态设置时间戳
        if status == BacktestStatus.RUNNING:
            update_data["started_at"] = datetime.now()
        elif status == BacktestStatus.COMPLETED:
            update_data["completed_at"] = datetime.now()
        
        update_data.update(kwargs)
        return await self.update(session, backtest_id, **update_data)


class TradeRecordRepository(BaseRepository[TradeRecord]):
    """交易记录仓库"""
    
    def __init__(self):
        super().__init__(TradeRecord)
    
    async def get_by_backtest(
        self, 
        session: AsyncSession, 
        backtest_id: int,
        symbol: Optional[str] = None
    ) -> List[TradeRecord]:
        """根据回测获取交易记录"""
        try:
            query = select(TradeRecord).where(TradeRecord.backtest_result_id == backtest_id)
            
            if symbol:
                query = query.where(TradeRecord.symbol == symbol)
            
            query = query.order_by(TradeRecord.trade_time)
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_backtest", "backtest_id": backtest_id})
            raise
    
    async def get_by_date_range(
        self, 
        session: AsyncSession,
        backtest_id: int,
        start_date: date,
        end_date: date
    ) -> List[TradeRecord]:
        """根据日期范围获取交易记录"""
        try:
            result = await session.execute(
                select(TradeRecord)
                .where(
                    and_(
                        TradeRecord.backtest_result_id == backtest_id,
                        TradeRecord.trade_date >= start_date,
                        TradeRecord.trade_date <= end_date
                    )
                )
                .order_by(TradeRecord.trade_time)
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_date_range", "backtest_id": backtest_id})
            raise
    
    async def create_batch(
        self, 
        session: AsyncSession, 
        trade_records: List[Dict[str, Any]]
    ) -> List[TradeRecord]:
        """批量创建交易记录"""
        try:
            records = [TradeRecord(**record_data) for record_data in trade_records]
            session.add_all(records)
            await session.flush()
            
            for record in records:
                await session.refresh(record)
            
            return records
        except Exception as e:
            self.log_error(e, {"method": "create_batch", "count": len(trade_records)})
            raise


class PositionRecordRepository(BaseRepository[PositionRecord]):
    """持仓记录仓库"""
    
    def __init__(self):
        super().__init__(PositionRecord)
    
    async def get_by_backtest(
        self, 
        session: AsyncSession, 
        backtest_id: int,
        record_date: Optional[date] = None
    ) -> List[PositionRecord]:
        """根据回测获取持仓记录"""
        try:
            query = select(PositionRecord).where(PositionRecord.backtest_result_id == backtest_id)
            
            if record_date:
                query = query.where(PositionRecord.record_date == record_date)
            
            query = query.order_by(PositionRecord.record_date, PositionRecord.symbol)
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_backtest", "backtest_id": backtest_id})
            raise
    
    async def get_latest_positions(
        self, 
        session: AsyncSession, 
        backtest_id: int
    ) -> List[PositionRecord]:
        """获取最新持仓记录"""
        try:
            # 子查询获取每个symbol的最新日期
            subquery = (
                select(
                    PositionRecord.symbol,
                    func.max(PositionRecord.record_date).label('max_date')
                )
                .where(PositionRecord.backtest_result_id == backtest_id)
                .group_by(PositionRecord.symbol)
                .subquery()
            )
            
            # 主查询获取最新持仓
            result = await session.execute(
                select(PositionRecord)
                .join(
                    subquery,
                    and_(
                        PositionRecord.symbol == subquery.c.symbol,
                        PositionRecord.record_date == subquery.c.max_date
                    )
                )
                .where(PositionRecord.backtest_result_id == backtest_id)
                .order_by(PositionRecord.symbol)
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_latest_positions", "backtest_id": backtest_id})
            raise


class SecurityInfoRepository(BaseRepository[SecurityInfo]):
    """证券信息仓库"""
    
    def __init__(self):
        super().__init__(SecurityInfo)
    
    async def get_by_symbol(self, session: AsyncSession, symbol: str) -> Optional[SecurityInfo]:
        """根据代码获取证券信息"""
        try:
            result = await session.execute(
                select(SecurityInfo).where(SecurityInfo.symbol == symbol)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.log_error(e, {"method": "get_by_symbol", "symbol": symbol})
            raise
    
    async def get_by_type(self, session: AsyncSession, security_type: str) -> List[SecurityInfo]:
        """根据类型获取证券信息"""
        try:
            result = await session.execute(
                select(SecurityInfo)
                .where(SecurityInfo.security_type == security_type)
                .where(SecurityInfo.is_active == True)
                .order_by(SecurityInfo.symbol)
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_by_type", "type": security_type})
            raise
    
    async def search_securities(
        self, 
        session: AsyncSession, 
        keyword: str,
        security_type: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> List[SecurityInfo]:
        """搜索证券"""
        try:
            query = select(SecurityInfo).where(
                or_(
                    SecurityInfo.symbol.ilike(f"%{keyword}%"),
                    SecurityInfo.name.ilike(f"%{keyword}%")
                )
            )
            
            if security_type:
                query = query.where(SecurityInfo.security_type == security_type)
            if exchange:
                query = query.where(SecurityInfo.exchange == exchange)
            
            query = query.where(SecurityInfo.is_active == True).order_by(SecurityInfo.symbol)
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "search_securities", "keyword": keyword})
            raise


class SystemLogRepository(BaseRepository[SystemLog]):
    """系统日志仓库"""
    
    def __init__(self):
        super().__init__(SystemLog)
    
    async def create_log(
        self, 
        session: AsyncSession,
        level: str,
        message: str,
        module: Optional[str] = None,
        function: Optional[str] = None,
        user_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> SystemLog:
        """创建日志记录"""
        return await self.create(
            session,
            level=level,
            message=message,
            module=module,
            function=function,
            user_id=user_id,
            extra_data=extra_data
        )
    
    async def get_logs_by_level(
        self, 
        session: AsyncSession, 
        level: str,
        limit: int = 100
    ) -> List[SystemLog]:
        """根据级别获取日志"""
        try:
            result = await session.execute(
                select(SystemLog)
                .where(SystemLog.level == level)
                .order_by(desc(SystemLog.created_at))
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            self.log_error(e, {"method": "get_logs_by_level", "level": level})
            raise
    
    async def cleanup_old_logs(self, session: AsyncSession, days: int = 30) -> int:
        """清理旧日志"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            result = await session.execute(
                delete(SystemLog).where(SystemLog.created_at < cutoff_date)
            )
            return result.rowcount
        except Exception as e:
            self.log_error(e, {"method": "cleanup_old_logs", "days": days})
            raise


# 仓库工厂类
class RepositoryFactory:
    """仓库工厂"""
    
    _repositories = {
        'user': UserRepository,
        'strategy': StrategyRepository,
        'backtest_result': BacktestResultRepository,
        'trade_record': TradeRecordRepository,
        'position_record': PositionRecordRepository,
        'security_info': SecurityInfoRepository,
        'system_log': SystemLogRepository,
    }
    
    @classmethod
    def get_repository(cls, name: str):
        """获取仓库实例"""
        if name not in cls._repositories:
            raise ValueError(f"Unknown repository: {name}")
        
        return cls._repositories[name]()
    
    @classmethod
    def get_user_repository(cls) -> UserRepository:
        """获取用户仓库"""
        return cls.get_repository('user')
    
    @classmethod
    def get_strategy_repository(cls) -> StrategyRepository:
        """获取策略仓库"""
        return cls.get_repository('strategy')
    
    @classmethod
    def get_backtest_repository(cls) -> BacktestResultRepository:
        """获取回测仓库"""
        return cls.get_repository('backtest_result')
    
    @classmethod
    def get_trade_repository(cls) -> TradeRecordRepository:
        """获取交易记录仓库"""
        return cls.get_repository('trade_record')
    
    @classmethod
    def get_position_repository(cls) -> PositionRecordRepository:
        """获取持仓记录仓库"""
        return cls.get_repository('position_record')
    
    @classmethod
    def get_security_repository(cls) -> SecurityInfoRepository:
        """获取证券信息仓库"""
        return cls.get_repository('security_info')
    
    @classmethod
    def get_log_repository(cls) -> SystemLogRepository:
        """获取日志仓库"""
        return cls.get_repository('system_log')