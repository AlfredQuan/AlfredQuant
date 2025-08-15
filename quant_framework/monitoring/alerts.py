"""
告警系统
"""

import asyncio
import json
import smtplib
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
from collections import defaultdict, deque

from .logger import get_logger
from ..core.config import get_settings

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """告警严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """告警状态"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertChannel(str, Enum):
    """告警渠道"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    SLACK = "slack"
    DINGTALK = "dingtalk"


@dataclass
class Alert:
    """告警"""
    id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    metrics: Dict[str, Any]
    threshold: float
    actual_value: float
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    description: str
    metric_name: str
    condition: str  # >, <, >=, <=, ==, !=
    threshold: float
    severity: AlertSeverity
    duration: int  # 持续时间（秒）
    channels: List[AlertChannel]
    enabled: bool = True
    tags: Optional[Dict[str, str]] = None
    
    def evaluate(self, value: float) -> bool:
        """评估规则"""
        if self.condition == '>':
            return value > self.threshold
        elif self.condition == '<':
            return value < self.threshold
        elif self.condition == '>=':
            return value >= self.threshold
        elif self.condition == '<=':
            return value <= self.threshold
        elif self.condition == '==':
            return value == self.threshold
        elif self.condition == '!=':
            return value != self.threshold
        else:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class AlertNotifier:
    """告警通知器"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def send_email(self, alert: Alert, recipients: List[str]) -> bool:
        """发送邮件告警"""
        try:
            # 创建邮件内容
            subject = f"[{alert.severity.upper()}] {alert.title}"
            
            html_content = f"""
            <html>
            <body>
                <h2>告警通知</h2>
                <p><strong>规则名称:</strong> {alert.rule_name}</p>
                <p><strong>严重程度:</strong> {alert.severity.upper()}</p>
                <p><strong>状态:</strong> {alert.status.upper()}</p>
                <p><strong>描述:</strong> {alert.description}</p>
                <p><strong>阈值:</strong> {alert.threshold}</p>
                <p><strong>实际值:</strong> {alert.actual_value}</p>
                <p><strong>触发时间:</strong> {alert.created_at}</p>
                
                <h3>相关指标</h3>
                <pre>{json.dumps(alert.metrics, indent=2, ensure_ascii=False)}</pre>
            </body>
            </html>
            """
            
            # 发送邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.settings.SMTP_FROM_EMAIL
            msg['To'] = ', '.join(recipients)
            
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT) as server:
                if self.settings.SMTP_USE_TLS:
                    server.starttls()
                
                if self.settings.SMTP_USERNAME and self.settings.SMTP_PASSWORD:
                    server.login(self.settings.SMTP_USERNAME, self.settings.SMTP_PASSWORD)
                
                server.send_message(msg)
            
            logger.info(f"邮件告警发送成功: {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"邮件告警发送失败: {e}")
            return False
    
    async def send_webhook(self, alert: Alert, webhook_url: str) -> bool:
        """发送Webhook告警"""
        try:
            payload = {
                'alert': alert.to_dict(),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            response.raise_for_status()
            
            logger.info(f"Webhook告警发送成功: {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Webhook告警发送失败: {e}")
            return False
    
    async def send_slack(self, alert: Alert, webhook_url: str) -> bool:
        """发送Slack告警"""
        try:
            # Slack消息格式
            color_map = {
                AlertSeverity.LOW: "good",
                AlertSeverity.MEDIUM: "warning", 
                AlertSeverity.HIGH: "danger",
                AlertSeverity.CRITICAL: "danger"
            }
            
            payload = {
                "attachments": [
                    {
                        "color": color_map.get(alert.severity, "warning"),
                        "title": alert.title,
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "规则名称",
                                "value": alert.rule_name,
                                "short": True
                            },
                            {
                                "title": "严重程度",
                                "value": alert.severity.upper(),
                                "short": True
                            },
                            {
                                "title": "阈值",
                                "value": str(alert.threshold),
                                "short": True
                            },
                            {
                                "title": "实际值",
                                "value": str(alert.actual_value),
                                "short": True
                            }
                        ],
                        "ts": int(datetime.fromisoformat(alert.created_at.replace('Z', '+00:00')).timestamp())
                    }
                ]
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            
            logger.info(f"Slack告警发送成功: {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Slack告警发送失败: {e}")
            return False
    
    async def send_dingtalk(self, alert: Alert, webhook_url: str) -> bool:
        """发送钉钉告警"""
        try:
            # 钉钉消息格式
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"告警通知: {alert.title}",
                    "text": f"""
## 告警通知

**规则名称:** {alert.rule_name}

**严重程度:** {alert.severity.upper()}

**状态:** {alert.status.upper()}

**描述:** {alert.description}

**阈值:** {alert.threshold}

**实际值:** {alert.actual_value}

**触发时间:** {alert.created_at}
                    """
                }
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            
            logger.info(f"钉钉告警发送成功: {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"钉钉告警发送失败: {e}")
            return False


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.rule_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        self.notifier = AlertNotifier()
        self.running = False
        self.thread = None
        
        # 告警抑制
        self.suppression_rules: Dict[str, Dict[str, Any]] = {}
        
        # 告警回调
        self.callbacks: List[Callable[[Alert], None]] = []
    
    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        self.rules[rule.name] = rule
        logger.info(f"告警规则已添加: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """移除告警规则"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            # 清理相关状态
            if rule_name in self.rule_states:
                del self.rule_states[rule_name]
            logger.info(f"告警规则已移除: {rule_name}")
            return True
        return False
    
    def enable_rule(self, rule_name: str) -> bool:
        """启用告警规则"""
        if rule_name in self.rules:
            self.rules[rule_name].enabled = True
            logger.info(f"告警规则已启用: {rule_name}")
            return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """禁用告警规则"""
        if rule_name in self.rules:
            self.rules[rule_name].enabled = False
            logger.info(f"告警规则已禁用: {rule_name}")
            return True
        return False
    
    def add_suppression_rule(
        self,
        name: str,
        start_time: datetime,
        end_time: datetime,
        rule_names: Optional[List[str]] = None,
        reason: str = ""
    ) -> None:
        """添加告警抑制规则"""
        self.suppression_rules[name] = {
            'start_time': start_time,
            'end_time': end_time,
            'rule_names': rule_names or [],
            'reason': reason
        }
        logger.info(f"告警抑制规则已添加: {name}")
    
    def remove_suppression_rule(self, name: str) -> bool:
        """移除告警抑制规则"""
        if name in self.suppression_rules:
            del self.suppression_rules[name]
            logger.info(f"告警抑制规则已移除: {name}")
            return True
        return False
    
    def is_suppressed(self, rule_name: str) -> bool:
        """检查告警是否被抑制"""
        now = datetime.utcnow()
        
        for suppression in self.suppression_rules.values():
            if suppression['start_time'] <= now <= suppression['end_time']:
                # 检查是否适用于此规则
                if not suppression['rule_names'] or rule_name in suppression['rule_names']:
                    return True
        
        return False
    
    def add_callback(self, callback: Callable[[Alert], None]) -> None:
        """添加告警回调函数"""
        self.callbacks.append(callback)
    
    def evaluate_metrics(self, metrics: Dict[str, Any]) -> None:
        """评估指标并触发告警"""
        current_time = datetime.utcnow()
        
        for rule_name, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            # 检查是否被抑制
            if self.is_suppressed(rule_name):
                continue
            
            # 获取指标值
            metric_value = self._extract_metric_value(metrics, rule.metric_name)
            if metric_value is None:
                continue
            
            # 评估规则
            is_triggered = rule.evaluate(metric_value)
            
            # 获取规则状态
            rule_state = self.rule_states[rule_name]
            
            if is_triggered:
                # 记录触发时间
                if 'first_triggered' not in rule_state:
                    rule_state['first_triggered'] = current_time
                
                # 检查持续时间
                duration = (current_time - rule_state['first_triggered']).total_seconds()
                
                if duration >= rule.duration:
                    # 创建或更新告警
                    alert_id = f"{rule_name}_{int(current_time.timestamp())}"
                    
                    if rule_name not in self.active_alerts:
                        alert = Alert(
                            id=alert_id,
                            rule_name=rule_name,
                            severity=rule.severity,
                            status=AlertStatus.ACTIVE,
                            title=f"{rule.description}",
                            description=f"指标 {rule.metric_name} 的值 {metric_value} {rule.condition} {rule.threshold}",
                            metrics=metrics,
                            threshold=rule.threshold,
                            actual_value=metric_value,
                            created_at=current_time.isoformat() + 'Z',
                            updated_at=current_time.isoformat() + 'Z'
                        )
                        
                        self.active_alerts[rule_name] = alert
                        self.alert_history.append(alert)
                        
                        # 发送告警通知
                        asyncio.create_task(self._send_alert_notifications(alert, rule))
                        
                        # 调用回调函数
                        for callback in self.callbacks:
                            try:
                                callback(alert)
                            except Exception as e:
                                logger.error(f"告警回调函数执行失败: {e}")
                        
                        logger.warning(f"告警触发: {rule_name}", extra={
                            'alert_id': alert_id,
                            'metric_name': rule.metric_name,
                            'threshold': rule.threshold,
                            'actual_value': metric_value
                        })
                    else:
                        # 更新现有告警
                        alert = self.active_alerts[rule_name]
                        alert.actual_value = metric_value
                        alert.updated_at = current_time.isoformat() + 'Z'
                        alert.metrics = metrics
            else:
                # 重置触发状态
                if 'first_triggered' in rule_state:
                    del rule_state['first_triggered']
                
                # 解决告警
                if rule_name in self.active_alerts:
                    alert = self.active_alerts[rule_name]
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = current_time.isoformat() + 'Z'
                    alert.updated_at = current_time.isoformat() + 'Z'
                    
                    # 发送解决通知
                    asyncio.create_task(self._send_resolution_notifications(alert, rule))
                    
                    # 从活跃告警中移除
                    del self.active_alerts[rule_name]
                    
                    logger.info(f"告警已解决: {rule_name}", extra={
                        'alert_id': alert.id
                    })
    
    def _extract_metric_value(self, metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        """从指标中提取值"""
        try:
            # 支持嵌套路径，如 system.cpu_percent
            keys = metric_name.split('.')
            value = metrics
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            
            return float(value) if value is not None else None
            
        except (ValueError, TypeError, KeyError):
            return None
    
    async def _send_alert_notifications(self, alert: Alert, rule: AlertRule) -> None:
        """发送告警通知"""
        settings = get_settings()
        
        for channel in rule.channels:
            try:
                if channel == AlertChannel.EMAIL:
                    recipients = getattr(settings, 'ALERT_EMAIL_RECIPIENTS', [])
                    if recipients:
                        await self.notifier.send_email(alert, recipients)
                
                elif channel == AlertChannel.WEBHOOK:
                    webhook_url = getattr(settings, 'ALERT_WEBHOOK_URL', None)
                    if webhook_url:
                        await self.notifier.send_webhook(alert, webhook_url)
                
                elif channel == AlertChannel.SLACK:
                    slack_url = getattr(settings, 'ALERT_SLACK_WEBHOOK_URL', None)
                    if slack_url:
                        await self.notifier.send_slack(alert, slack_url)
                
                elif channel == AlertChannel.DINGTALK:
                    dingtalk_url = getattr(settings, 'ALERT_DINGTALK_WEBHOOK_URL', None)
                    if dingtalk_url:
                        await self.notifier.send_dingtalk(alert, dingtalk_url)
                
            except Exception as e:
                logger.error(f"发送告警通知失败 ({channel}): {e}")
    
    async def _send_resolution_notifications(self, alert: Alert, rule: AlertRule) -> None:
        """发送告警解决通知"""
        # 创建解决通知
        resolution_alert = Alert(
            id=alert.id + "_resolved",
            rule_name=alert.rule_name,
            severity=alert.severity,
            status=AlertStatus.RESOLVED,
            title=f"[已解决] {alert.title}",
            description=f"告警已解决: {alert.description}",
            metrics=alert.metrics,
            threshold=alert.threshold,
            actual_value=alert.actual_value,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            resolved_at=alert.resolved_at
        )
        
        await self._send_alert_notifications(resolution_alert, rule)
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        return list(self.alert_history)[-limit:]
    
    def get_rules(self) -> List[AlertRule]:
        """获取所有规则"""
        return list(self.rules.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取告警统计"""
        total_rules = len(self.rules)
        enabled_rules = sum(1 for rule in self.rules.values() if rule.enabled)
        active_alerts = len(self.active_alerts)
        
        # 按严重程度统计
        severity_counts = defaultdict(int)
        for alert in self.active_alerts.values():
            severity_counts[alert.severity] += 1
        
        return {
            'total_rules': total_rules,
            'enabled_rules': enabled_rules,
            'active_alerts': active_alerts,
            'severity_counts': dict(severity_counts),
            'suppression_rules': len(self.suppression_rules)
        }


# 全局告警管理器实例
alert_manager = AlertManager()


# 预定义告警规则
def setup_default_alert_rules():
    """设置默认告警规则"""
    
    # CPU使用率告警
    alert_manager.add_rule(AlertRule(
        name="high_cpu_usage",
        description="CPU使用率过高",
        metric_name="system.cpu_percent",
        condition=">",
        threshold=80.0,
        severity=AlertSeverity.HIGH,
        duration=300,  # 5分钟
        channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK]
    ))
    
    # 内存使用率告警
    alert_manager.add_rule(AlertRule(
        name="high_memory_usage",
        description="内存使用率过高",
        metric_name="system.memory_percent",
        condition=">",
        threshold=85.0,
        severity=AlertSeverity.HIGH,
        duration=300,
        channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK]
    ))
    
    # 磁盘使用率告警
    alert_manager.add_rule(AlertRule(
        name="high_disk_usage",
        description="磁盘使用率过高",
        metric_name="system.disk_usage_percent",
        condition=">",
        threshold=90.0,
        severity=AlertSeverity.CRITICAL,
        duration=60,
        channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK, AlertChannel.SLACK]
    ))
    
    # 响应时间告警
    alert_manager.add_rule(AlertRule(
        name="high_response_time",
        description="API响应时间过长",
        metric_name="application.response_time_avg",
        condition=">",
        threshold=2.0,  # 2秒
        severity=AlertSeverity.MEDIUM,
        duration=180,
        channels=[AlertChannel.EMAIL]
    ))
    
    # 错误率告警
    alert_manager.add_rule(AlertRule(
        name="high_error_rate",
        description="错误率过高",
        metric_name="application.error_rate",
        condition=">",
        threshold=0.05,  # 5%
        severity=AlertSeverity.HIGH,
        duration=120,
        channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
    ))
    
    logger.info("默认告警规则已设置")