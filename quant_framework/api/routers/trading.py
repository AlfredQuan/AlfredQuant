"""
交易路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter()


class OrderRequest(BaseModel):
    """下单请求模型"""
    symbol: str
    side: str  # buy, sell
    quantity: float
    order_type: str = "market"  # market, limit, stop
    price: Optional[float] = None


class OrderResponse(BaseModel):
    """订单响应模型"""
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    price: Optional[float]
    status: str
    created_at: datetime
    filled_at: Optional[datetime] = None


class PositionResponse(BaseModel):
    """持仓响应模型"""
    symbol: str
    quantity: float
    avg_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


class PortfolioResponse(BaseModel):
    """投资组合响应模型"""
    cash: float
    total_value: float
    positions: List[PositionResponse]
    daily_pnl: float
    status: str


# 模拟交易数据
orders_db = {}
portfolio_data = {
    "cash": 1000000.0,
    "total_value": 1000000.0,
    "positions": {},
    "daily_pnl": 0.0,
    "status": "active"
}


@router.post("/trading/orders", response_model=OrderResponse)
async def place_order(order_request: OrderRequest):
    """下单"""
    order_id = f"order_{len(orders_db) + 1}"
    
    order = OrderResponse(
        order_id=order_id,
        symbol=order_request.symbol,
        side=order_request.side,
        quantity=order_request.quantity,
        order_type=order_request.order_type,
        price=order_request.price,
        status="pending",
        created_at=datetime.now()
    )
    
    orders_db[order_id] = order
    
    # 模拟立即执行市价单
    if order_request.order_type == "market":
        order.status = "filled"
        order.filled_at = datetime.now()
        
        # 更新持仓（简化处理）
        if order_request.symbol not in portfolio_data["positions"]:
            portfolio_data["positions"][order_request.symbol] = {
                "quantity": 0.0,
                "avg_price": 0.0,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0
            }
        
        position = portfolio_data["positions"][order_request.symbol]
        
        if order_request.side == "buy":
            position["quantity"] += order_request.quantity
            portfolio_data["cash"] -= order_request.quantity * 100  # 假设价格为100
        else:
            position["quantity"] -= order_request.quantity
            portfolio_data["cash"] += order_request.quantity * 100
    
    return order


@router.get("/trading/orders", response_model=List[OrderResponse])
async def list_orders():
    """获取订单列表"""
    return list(orders_db.values())


@router.get("/trading/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """获取特定订单"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return orders_db[order_id]


@router.delete("/trading/orders/{order_id}")
async def cancel_order(order_id: str):
    """取消订单"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    if order.status == "filled":
        raise HTTPException(status_code=400, detail="Cannot cancel filled order")
    
    order.status = "cancelled"
    return {"message": "Order cancelled successfully"}


@router.get("/trading/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """获取投资组合"""
    positions = []
    for symbol, pos_data in portfolio_data["positions"].items():
        if pos_data["quantity"] != 0:
            positions.append(PositionResponse(
                symbol=symbol,
                quantity=pos_data["quantity"],
                avg_price=pos_data["avg_price"],
                market_value=pos_data["market_value"],
                unrealized_pnl=pos_data["unrealized_pnl"],
                realized_pnl=pos_data["realized_pnl"]
            ))
    
    return PortfolioResponse(
        cash=portfolio_data["cash"],
        total_value=portfolio_data["total_value"],
        positions=positions,
        daily_pnl=portfolio_data["daily_pnl"],
        status=portfolio_data["status"]
    )


@router.get("/trading/positions")
async def get_positions():
    """获取持仓列表"""
    positions = []
    for symbol, pos_data in portfolio_data["positions"].items():
        if pos_data["quantity"] != 0:
            positions.append({
                "symbol": symbol,
                "quantity": pos_data["quantity"],
                "avg_price": pos_data["avg_price"],
                "market_value": pos_data["market_value"],
                "unrealized_pnl": pos_data["unrealized_pnl"]
            })
    
    return positions


@router.get("/trading/status")
async def get_trading_status():
    """获取交易状态"""
    return {
        "status": "active",
        "mode": "simulation",
        "total_orders": len(orders_db),
        "active_positions": len([pos for pos in portfolio_data["positions"].values() if pos["quantity"] != 0]),
        "cash": portfolio_data["cash"],
        "total_value": portfolio_data["total_value"]
    }