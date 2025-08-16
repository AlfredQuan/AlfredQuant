"""
策略管理路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter()


class StrategyCreate(BaseModel):
    """创建策略请求模型"""
    name: str
    description: Optional[str] = None
    code: str
    parameters: Optional[Dict[str, Any]] = None


class StrategyResponse(BaseModel):
    """策略响应模型"""
    id: str
    name: str
    description: Optional[str]
    code: str
    parameters: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    status: str


# 模拟策略存储
strategies_db = {}


@router.get("/strategies", response_model=List[StrategyResponse])
async def list_strategies():
    """获取策略列表"""
    return list(strategies_db.values())


@router.post("/strategies", response_model=StrategyResponse)
async def create_strategy(strategy: StrategyCreate):
    """创建新策略"""
    strategy_id = f"strategy_{len(strategies_db) + 1}"
    
    new_strategy = StrategyResponse(
        id=strategy_id,
        name=strategy.name,
        description=strategy.description,
        code=strategy.code,
        parameters=strategy.parameters,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        status="active"
    )
    
    strategies_db[strategy_id] = new_strategy
    return new_strategy


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str):
    """获取特定策略"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategies_db[strategy_id]


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(strategy_id: str, strategy: StrategyCreate):
    """更新策略"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    existing_strategy = strategies_db[strategy_id]
    updated_strategy = StrategyResponse(
        id=strategy_id,
        name=strategy.name,
        description=strategy.description,
        code=strategy.code,
        parameters=strategy.parameters,
        created_at=existing_strategy.created_at,
        updated_at=datetime.now(),
        status=existing_strategy.status
    )
    
    strategies_db[strategy_id] = updated_strategy
    return updated_strategy


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    del strategies_db[strategy_id]
    return {"message": "Strategy deleted successfully"}


@router.post("/strategies/{strategy_id}/validate")
async def validate_strategy(strategy_id: str):
    """验证策略代码"""
    if strategy_id not in strategies_db:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy = strategies_db[strategy_id]
    
    # 简单的代码验证
    try:
        compile(strategy.code, '<string>', 'exec')
        return {"valid": True, "message": "Strategy code is valid"}
    except SyntaxError as e:
        return {"valid": False, "message": f"Syntax error: {str(e)}"}
    except Exception as e:
        return {"valid": False, "message": f"Validation error: {str(e)}"}