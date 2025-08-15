"""
通知相关的异步任务
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import current_task
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from .celery_app import celery_app
from .task_models import TaskStatus
from ..core.config import get_settings
from ..core.database import get_db_session
from ..trading.notification import NotificationService
import logging
import traceback
import json
import requests

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='send_notification_task')
def send_notification_task(
    self,
    recipient: str,
    title: str,
    content: str,
    notification_type: str = 'info',
    channels: List[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """发送通知任务"""
    
    task_id = self.request.id
    logger.info(f"Starting notification task {task_id} for {recipient}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '开始发送通知...'}
        )
        
        # 默认通知渠道
        if not channels:
            channels = ['websocket']
        
        # 初始化通知服务
        notification_service = NotificationService()
        
        results = {}
        total_channels = len(channels)
        
        for i, channel in enumerate(channels):
            # 更新进度
            progress = (i / total_channels) * 100
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={
                    'progress': progress,
                    'message': f'发送通知到 {channel}...',
                    'current_channel': channel
                }
            )
            
            try:
                if channel == 'websocket':
                    # WebSocket通知
                    result = notification_service.send_websocket_notification(
                        recipient=recipient,
                        title=title,
                        content=content,
                        notification_type=notification_type,
                        data=data
                    )
                    
                elif channel == 'email':
                    # 邮件通知
                    result = send_email_task.apply_async(
                        args=[recipient, title, content],
                        kwargs={'data': data}
                    ).get()
                    
                elif channel == 'sms':
                    # 短信通知
                    result = send_sms_task.apply_async(
                        args=[recipient, content]
                    ).get()
                    
                elif channel == 'webhook':
                    # Webhook通知
                    result = send_webhook_task.apply_async(
                        args=[recipient, title, content],
                        kwargs={'data': data}
                    ).get()
                    
                else:
                    raise ValueError(f"不支持的通知渠道: {channel}")
                
                results[channel] = {
                    'status': 'success',
                    'result': result
                }
                
            except Exception as e:
                logger.error(f"Failed to send notification via {channel}: {e}")
                results[channel] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        # 统计结果
        successful = len([r for r in results.values() if r['status'] == 'success'])
        failed = len([r for r in results.values() if r['status'] == 'failed'])
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': f'通知发送完成: 成功 {successful}, 失败 {failed}',
                'result': {
                    'recipient': recipient,
                    'title': title,
                    'channels': channels,
                    'successful': successful,
                    'failed': failed,
                    'results': results
                }
            }
        )
        
        logger.info(f"Notification task {task_id} completed")
        
        return {
            'recipient': recipient,
            'title': title,
            'channels': channels,
            'successful': successful,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Notification task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'通知发送失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='send_email_task')
def send_email_task(
    self,
    recipient: str,
    subject: str,
    content: str,
    content_type: str = 'html',
    attachments: Optional[List[Dict[str, Any]]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """发送邮件任务"""
    
    task_id = self.request.id
    logger.info(f"Starting email task {task_id} to {recipient}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '准备发送邮件...'}
        )
        
        # 获取邮件配置
        settings = get_settings()
        
        # 创建邮件消息
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # 添加邮件内容
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 25, 'message': '构建邮件内容...'}
        )
        
        if content_type == 'html':
            msg.attach(MIMEText(content, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
        
        # 添加附件
        if attachments:
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 50, 'message': '添加邮件附件...'}
            )
            
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment["filename"]}'
                )
                msg.attach(part)
        
        # 发送邮件
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 75, 'message': '发送邮件...'}
        )
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            
            server.send_message(msg)
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': '邮件发送成功',
                'result': {
                    'recipient': recipient,
                    'subject': subject,
                    'sent_at': datetime.utcnow().isoformat()
                }
            }
        )
        
        logger.info(f"Email task {task_id} completed")
        
        return {
            'recipient': recipient,
            'subject': subject,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Email task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'邮件发送失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='send_sms_task')
def send_sms_task(
    self,
    phone_number: str,
    message: str,
    template_id: Optional[str] = None,
    template_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """发送短信任务"""
    
    task_id = self.request.id
    logger.info(f"Starting SMS task {task_id} to {phone_number}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '准备发送短信...'}
        )
        
        # 获取短信配置
        settings = get_settings()
        
        # 这里可以集成各种短信服务提供商
        # 例如：阿里云短信、腾讯云短信、华为云短信等
        
        # 示例：使用HTTP API发送短信
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 50, 'message': '发送短信...'}
        )
        
        # TODO: 实现具体的短信发送逻辑
        # 这里使用模拟发送
        import time
        time.sleep(1)  # 模拟网络延迟
        
        # 模拟成功响应
        sms_result = {
            'message_id': f"sms_{task_id}_{int(datetime.utcnow().timestamp())}",
            'status': 'sent',
            'phone_number': phone_number,
            'sent_at': datetime.utcnow().isoformat()
        }
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': '短信发送成功',
                'result': sms_result
            }
        )
        
        logger.info(f"SMS task {task_id} completed")
        
        return sms_result
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"SMS task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'短信发送失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='send_webhook_task')
def send_webhook_task(
    self,
    webhook_url: str,
    title: str,
    content: str,
    method: str = 'POST',
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """发送Webhook通知任务"""
    
    task_id = self.request.id
    logger.info(f"Starting webhook task {task_id} to {webhook_url}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '准备发送Webhook...'}
        )
        
        # 准备请求数据
        payload = {
            'title': title,
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data or {}
        }
        
        # 默认请求头
        if not headers:
            headers = {'Content-Type': 'application/json'}
        
        # 发送Webhook
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 50, 'message': '发送Webhook请求...'}
        )
        
        if method.upper() == 'POST':
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )
        elif method.upper() == 'PUT':
            response = requests.put(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")
        
        # 检查响应
        response.raise_for_status()
        
        webhook_result = {
            'webhook_url': webhook_url,
            'method': method,
            'status_code': response.status_code,
            'response': response.text[:1000],  # 限制响应长度
            'sent_at': datetime.utcnow().isoformat()
        }
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': 'Webhook发送成功',
                'result': webhook_result
            }
        )
        
        logger.info(f"Webhook task {task_id} completed")
        
        return webhook_result
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Webhook task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'Webhook发送失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='batch_notification_task')
def batch_notification_task(
    self,
    recipients: List[str],
    title: str,
    content: str,
    notification_type: str = 'info',
    channels: List[str] = None
) -> Dict[str, Any]:
    """批量通知任务"""
    
    task_id = self.request.id
    logger.info(f"Starting batch notification task {task_id} for {len(recipients)} recipients")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '开始批量发送通知...'}
        )
        
        results = {}
        total_recipients = len(recipients)
        
        for i, recipient in enumerate(recipients):
            # 更新进度
            progress = (i / total_recipients) * 100
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={
                    'progress': progress,
                    'message': f'发送通知: {recipient} ({i+1}/{total_recipients})',
                    'current_recipient': recipient
                }
            )
            
            try:
                # 发送单个通知
                result = send_notification_task.apply_async(
                    args=[recipient, title, content, notification_type, channels]
                ).get()
                
                results[recipient] = {
                    'status': 'success',
                    'result': result
                }
                
            except Exception as e:
                logger.error(f"Failed to send notification to {recipient}: {e}")
                results[recipient] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        # 统计结果
        successful = len([r for r in results.values() if r['status'] == 'success'])
        failed = len([r for r in results.values() if r['status'] == 'failed'])
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': f'批量通知完成: 成功 {successful}, 失败 {failed}',
                'result': {
                    'total_recipients': total_recipients,
                    'successful': successful,
                    'failed': failed,
                    'results': results
                }
            }
        )
        
        logger.info(f"Batch notification task {task_id} completed")
        
        return {
            'total_recipients': total_recipients,
            'successful': successful,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Batch notification task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'批量通知失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise