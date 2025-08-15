"""
通知服务
提供多种通知方式的交易建议和状态推送
"""

import asyncio
import smtplib
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from abc import ABC, abstractmethod
import websockets
from dataclasses import dataclass

from quant_framework.core.config import NotificationConfig
from quant_framework.core.exceptions import NotificationError
from quant_framework.trading.service import TradingSignal, TradingRecord
from quant_framework.utils.logger import LoggerMixin


@dataclass
class NotificationMessage:
    """通知消息"""
    message_id: str
    title: str
    content: str
    message_type: str  # info, warning, error, signal, trade
    timestamp: datetime
    recipient: str
    data: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'message_id': self.message_id,
            'title': self.title,
            'content': self.content,
            'message_type': self.message_type,
            'timestamp': self.timestamp.isoformat(),
            'recipient': self.recipient,
            'data': self.data or {}
        }


class NotificationChannel(ABC, LoggerMixin):
    """通知渠道抽象基类"""
    
    @abstractmethod
    async def send_message(self, message: NotificationMessage) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查渠道是否可用"""
        pass


class EmailNotificationChannel(NotificationChannel):
    """邮件通知渠道"""
    
    def __init__(self, config: Dict[str, Any]):
        self.smtp_server = config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.from_email = config.get('from_email', self.username)
        self.use_tls = config.get('use_tls', True)
    
    async def send_message(self, message: NotificationMessage) -> bool:
        """发送邮件"""
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = message.recipient
            msg['Subject'] = message.title
            
            # 添加邮件正文
            body = self._format_email_body(message)
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            if self.use_tls:
                server.starttls()
            
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            self.logger.info(
                "Email sent successfully",
                recipient=message.recipient,
                title=message.title
            )
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "send_message",
                "recipient": message.recipient,
                "title": message.title
            })
            return False
    
    def is_available(self) -> bool:
        """检查邮件服务是否可用"""
        return bool(self.username and self.password and self.smtp_server)
    
    def _format_email_body(self, message: NotificationMessage) -> str:
        """格式化邮件正文"""
        html_template = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; }}
                .content {{ margin: 20px 0; }}
                .data {{ background-color: #f9f9f9; padding: 10px; border-left: 3px solid #007cba; }}
                .timestamp {{ color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{message.title}</h2>
                <div class="timestamp">时间: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            
            <div class="content">
                <p>{message.content}</p>
            </div>
            
            {self._format_data_section(message.data) if message.data else ''}
        </body>
        </html>
        """
        
        return html_template
    
    def _format_data_section(self, data: Dict[str, Any]) -> str:
        """格式化数据部分"""
        if not data:
            return ""
        
        data_html = "<div class='data'><h3>详细信息:</h3><ul>"
        
        for key, value in data.items():
            data_html += f"<li><strong>{key}:</strong> {value}</li>"
        
        data_html += "</ul></div>"
        
        return data_html


class WebSocketNotificationChannel(NotificationChannel):
    """WebSocket通知渠道"""
    
    def __init__(self, config: Dict[str, Any]):
        self.websocket_url = config.get('websocket_url', 'ws://localhost:8765')
        self.connected_clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.server = None
        self.is_running = False
    
    async def start_server(self, host: str = 'localhost', port: int = 8765):
        """启动WebSocket服务器"""
        try:
            self.server = await websockets.serve(
                self._handle_client,
                host,
                port
            )
            self.is_running = True
            
            self.logger.info(f"WebSocket server started on ws://{host}:{port}")
            
        except Exception as e:
            self.log_error(e, {"method": "start_server"})
            raise NotificationError(f"启动WebSocket服务器失败: {e}")
    
    async def stop_server(self):
        """停止WebSocket服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.is_running = False
            self.connected_clients.clear()
            
            self.logger.info("WebSocket server stopped")
    
    async def _handle_client(self, websocket, path):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.connected_clients[client_id] = websocket
        
        self.logger.info(f"Client connected: {client_id}")
        
        try:
            await websocket.wait_closed()
        finally:
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
            self.logger.info(f"Client disconnected: {client_id}")
    
    async def send_message(self, message: NotificationMessage) -> bool:
        """发送WebSocket消息"""
        try:
            if not self.connected_clients:
                self.logger.warning("No connected WebSocket clients")
                return False
            
            message_json = json.dumps(message.to_dict(), ensure_ascii=False)
            
            # 发送给所有连接的客户端
            disconnected_clients = []
            
            for client_id, websocket in self.connected_clients.items():
                try:
                    await websocket.send(message_json)
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.append(client_id)
                except Exception as e:
                    self.logger.warning(f"Failed to send message to client {client_id}: {e}")
                    disconnected_clients.append(client_id)
            
            # 清理断开的连接
            for client_id in disconnected_clients:
                if client_id in self.connected_clients:
                    del self.connected_clients[client_id]
            
            active_clients = len(self.connected_clients)
            
            self.logger.info(
                "WebSocket message sent",
                active_clients=active_clients,
                message_type=message.message_type
            )
            
            return active_clients > 0
            
        except Exception as e:
            self.log_error(e, {"method": "send_message"})
            return False
    
    def is_available(self) -> bool:
        """检查WebSocket服务是否可用"""
        return self.is_running and len(self.connected_clients) > 0


class SMSNotificationChannel(NotificationChannel):
    """短信通知渠道（模拟实现）"""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.service_url = config.get('service_url', '')
        self.enabled = config.get('enabled', False)
    
    async def send_message(self, message: NotificationMessage) -> bool:
        """发送短信（模拟实现）"""
        try:
            if not self.enabled:
                self.logger.info("SMS service is disabled")
                return False
            
            # 这里应该调用实际的短信服务API
            # 例如阿里云短信、腾讯云短信等
            
            # 模拟发送
            self.logger.info(
                "SMS sent (simulated)",
                recipient=message.recipient,
                content=message.content[:50] + "..." if len(message.content) > 50 else message.content
            )
            
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "send_message"})
            return False
    
    def is_available(self) -> bool:
        """检查短信服务是否可用"""
        return self.enabled and bool(self.api_key and self.api_secret)


class NotificationService(LoggerMixin):
    """通知服务"""
    
    def __init__(self, config: NotificationConfig = None):
        self.config = config or NotificationConfig()
        self.channels: Dict[str, NotificationChannel] = {}
        self.message_history: List[NotificationMessage] = []
        self.subscribers: Dict[str, List[str]] = {}  # 订阅者 -> 渠道列表
        
        # 初始化通知渠道
        self._initialize_channels()
        
        # 统计信息
        self.stats = {
            'total_messages': 0,
            'successful_sends': 0,
            'failed_sends': 0,
            'start_time': datetime.now()
        }
    
    def _initialize_channels(self):
        """初始化通知渠道"""
        # 邮件渠道
        if hasattr(self.config, 'email') and self.config.email:
            email_channel = EmailNotificationChannel(self.config.email)
            if email_channel.is_available():
                self.channels['email'] = email_channel
                self.logger.info("Email notification channel initialized")
        
        # WebSocket渠道
        if hasattr(self.config, 'websocket') and self.config.websocket:
            websocket_channel = WebSocketNotificationChannel(self.config.websocket)
            self.channels['websocket'] = websocket_channel
            self.logger.info("WebSocket notification channel initialized")
        
        # 短信渠道
        if hasattr(self.config, 'sms') and self.config.sms:
            sms_channel = SMSNotificationChannel(self.config.sms)
            if sms_channel.is_available():
                self.channels['sms'] = sms_channel
                self.logger.info("SMS notification channel initialized")
    
    async def start_service(self):
        """启动通知服务"""
        try:
            # 启动WebSocket服务器
            if 'websocket' in self.channels:
                websocket_channel = self.channels['websocket']
                await websocket_channel.start_server()
            
            self.logger.info("Notification service started")
            
        except Exception as e:
            self.log_error(e, {"method": "start_service"})
            raise NotificationError(f"启动通知服务失败: {e}")
    
    async def stop_service(self):
        """停止通知服务"""
        try:
            # 停止WebSocket服务器
            if 'websocket' in self.channels:
                websocket_channel = self.channels['websocket']
                await websocket_channel.stop_server()
            
            self.logger.info("Notification service stopped")
            
        except Exception as e:
            self.log_error(e, {"method": "stop_service"})
    
    async def send_notification(
        self,
        title: str,
        content: str,
        message_type: str = 'info',
        recipient: str = None,
        channels: List[str] = None,
        data: Dict[str, Any] = None
    ) -> bool:
        """
        发送通知
        
        Args:
            title: 标题
            content: 内容
            message_type: 消息类型
            recipient: 接收者
            channels: 指定渠道列表
            data: 附加数据
            
        Returns:
            是否发送成功
        """
        try:
            # 创建消息
            message = NotificationMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                title=title,
                content=content,
                message_type=message_type,
                timestamp=datetime.now(),
                recipient=recipient or 'default',
                data=data
            )
            
            # 确定发送渠道
            target_channels = channels or list(self.channels.keys())
            
            # 发送到各个渠道
            success_count = 0
            total_channels = len(target_channels)
            
            for channel_name in target_channels:
                if channel_name in self.channels:
                    channel = self.channels[channel_name]
                    
                    if channel.is_available():
                        success = await channel.send_message(message)
                        if success:
                            success_count += 1
                    else:
                        self.logger.warning(f"Channel {channel_name} is not available")
            
            # 记录消息历史
            self.message_history.append(message)
            
            # 更新统计
            self.stats['total_messages'] += 1
            if success_count > 0:
                self.stats['successful_sends'] += 1
            else:
                self.stats['failed_sends'] += 1
            
            # 限制历史记录数量
            if len(self.message_history) > 1000:
                self.message_history = self.message_history[-500:]
            
            self.logger.info(
                "Notification sent",
                title=title,
                message_type=message_type,
                channels_sent=success_count,
                total_channels=total_channels
            )
            
            return success_count > 0
            
        except Exception as e:
            self.log_error(e, {"method": "send_notification"})
            self.stats['failed_sends'] += 1
            return False
    
    async def send_signal_notification(self, signal: TradingSignal) -> bool:
        """发送交易信号通知"""
        title = f"交易信号 - {signal.symbol}"
        
        content = f"""
        策略ID: {signal.strategy_id}
        股票代码: {signal.symbol}
        信号类型: {signal.signal_type.value.upper()}
        数量: {signal.quantity}
        价格: {signal.price or '市价'}
        置信度: {signal.confidence:.2%}
        原因: {signal.reason}
        """
        
        data = {
            'signal_id': signal.signal_id,
            'strategy_id': signal.strategy_id,
            'symbol': signal.symbol,
            'signal_type': signal.signal_type.value,
            'quantity': signal.quantity,
            'price': float(signal.price) if signal.price else None,
            'confidence': signal.confidence
        }
        
        return await self.send_notification(
            title=title,
            content=content,
            message_type='signal',
            data=data
        )
    
    async def send_trade_notification(self, trade: TradingRecord) -> bool:
        """发送交易执行通知"""
        title = f"交易执行 - {trade.symbol}"
        
        content = f"""
        策略ID: {trade.strategy_id}
        股票代码: {trade.symbol}
        交易动作: {trade.action.value.upper()}
        数量: {trade.quantity}
        价格: {trade.price}
        金额: {trade.amount}
        手续费: {trade.commission}
        """
        
        data = {
            'record_id': trade.record_id,
            'strategy_id': trade.strategy_id,
            'symbol': trade.symbol,
            'action': trade.action.value,
            'quantity': trade.quantity,
            'price': float(trade.price),
            'amount': float(trade.amount),
            'commission': float(trade.commission)
        }
        
        return await self.send_notification(
            title=title,
            content=content,
            message_type='trade',
            data=data
        )
    
    def subscribe(self, subscriber: str, channels: List[str]):
        """订阅通知"""
        self.subscribers[subscriber] = channels
        self.logger.info(f"Subscriber {subscriber} subscribed to channels: {channels}")
    
    def unsubscribe(self, subscriber: str):
        """取消订阅"""
        if subscriber in self.subscribers:
            del self.subscribers[subscriber]
            self.logger.info(f"Subscriber {subscriber} unsubscribed")
    
    def get_message_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取消息历史"""
        recent_messages = sorted(
            self.message_history,
            key=lambda m: m.timestamp,
            reverse=True
        )[:limit]
        
        return [msg.to_dict() for msg in recent_messages]
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        current_time = datetime.now()
        uptime = (current_time - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'start_time': self.stats['start_time'].isoformat(),
            'available_channels': list(self.channels.keys()),
            'active_subscribers': len(self.subscribers),
            'success_rate': (self.stats['successful_sends'] / max(self.stats['total_messages'], 1)) * 100
        }


# 全局通知服务实例
_notification_service: Optional[NotificationService] = None


def initialize_notification_service(config: NotificationConfig = None) -> NotificationService:
    """初始化通知服务"""
    global _notification_service
    _notification_service = NotificationService(config)
    return _notification_service


def get_notification_service() -> NotificationService:
    """获取通知服务实例"""
    if _notification_service is None:
        raise RuntimeError("Notification service not initialized. Call initialize_notification_service() first.")
    return _notification_service