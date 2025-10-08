import asyncio
import datetime
import json
import logging
import sys
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect


class StreamToLogger:
    def __init__(self, logger_instance, log_level=logging.INFO):
        self.logger = logger_instance
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        try:
            temp_linebuf = self.linebuf + buf
            self.linebuf = ''
            for line in temp_linebuf.splitlines(True):
                if line.endswith(('\n', '\r')):
                    self.logger.log(self.log_level, line.rstrip())
                else:
                    self.linebuf += line
        except Exception as e:
            print(f"StreamToLogger hatası: {e}", file=sys.__stderr__)

    def flush(self):
        try:
            if self.linebuf != '':
                self.logger.log(self.log_level, self.linebuf.rstrip())
            self.linebuf = ''
        except Exception as e:
            print(f"StreamToLogger Flush hatası: {e}", file=sys.__stderr__)

    def isatty(self):
        return False


class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger = logging.getLogger("AIStudioProxyServer")
        logger.info(f"WebSocket log istemcisi bağlandı: {client_id}")
        try:
            await websocket.send_text(json.dumps({
                "type": "connection_status",
                "status": "connected",
                "message": "Gerçek zamanlı log akışına bağlandı.",
                "timestamp": datetime.datetime.now().isoformat()
            }))
        except Exception as e:
            logger.warning(f"WebSocket istemcisi {client_id} için karşılama mesajı gönderme başarısız: {e}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger = logging.getLogger("AIStudioProxyServer")
            logger.info(f"WebSocket log istemcisi bağlantıyı kesti: {client_id}")

    async def broadcast(self, message: str):
        if not self.active_connections:
            return
        disconnected_clients = []
        active_conns_copy = list(self.active_connections.items())
        logger = logging.getLogger("AIStudioProxyServer")
        for client_id, connection in active_conns_copy:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                logger.info(f"[WS Broadcast] İstemci {client_id} yayın sırasında bağlantıyı kesti.")
                disconnected_clients.append(client_id)
            except RuntimeError as e:
                 if "Connection is closed" in str(e):
                     logger.info(f"[WS Broadcast] İstemci {client_id} bağlantısı kapatıldı.")
                     disconnected_clients.append(client_id)
                 else:
                     logger.error(f"WebSocket {client_id} için yayın sırasında çalışma zamanı hatası: {e}")
                     disconnected_clients.append(client_id)
            except Exception as e:
                logger.error(f"WebSocket {client_id} için yayın sırasında bilinmeyen hata: {e}")
                disconnected_clients.append(client_id)
        if disconnected_clients:
             for client_id_to_remove in disconnected_clients:
                 self.disconnect(client_id_to_remove)


class WebSocketLogHandler(logging.Handler):
    def __init__(self, manager: WebSocketConnectionManager):
        super().__init__()
        self.manager = manager
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    def emit(self, record: logging.LogRecord):
        if self.manager and self.manager.active_connections:
            try:
                log_entry_str = self.format(record)
                try:
                     current_loop = asyncio.get_running_loop()
                     current_loop.create_task(self.manager.broadcast(log_entry_str))
                except RuntimeError:
                     pass
            except Exception as e:
                print(f"WebSocketLogHandler hatası: Log yayınlama başarısız - {e}", file=sys.__stderr__)