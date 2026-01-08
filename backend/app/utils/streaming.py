import asyncio
import json
from typing import AsyncGenerator, Optional
from collections import deque
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StreamBuffer:
    """Circular buffer for stream chunks"""
    
    def __init__(self, max_size: int = 1000):
        self.buffer = deque(maxlen=max_size)
        self.lock = asyncio.Lock()
    
    async def add(self, chunk: dict):
        """Add chunk to buffer"""
        async with self.lock:
            self.buffer.append({
                **chunk,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def get_recent(self, n: int = 10) -> list:
        """Get n most recent chunks"""
        async with self.lock:
            return list(self.buffer)[-n:]
    
    async def clear(self):
        """Clear buffer"""
        async with self.lock:
            self.buffer.clear()


class StreamManager:
    """Manage streaming with reconnection and error recovery"""
    
    def __init__(self, buffer_size: int = 1000):
        self.buffer = StreamBuffer(buffer_size)
        self.active_streams = {}
        self.reconnect_attempts = {}
        self.max_reconnect_attempts = 5
    
    async def create_stream(self, stream_id: str) -> str:
        """Create new stream"""
        self.active_streams[stream_id] = {
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "chunks_sent": 0
        }
        self.reconnect_attempts[stream_id] = 0
        return stream_id
    
    async def update_activity(self, stream_id: str):
        """Update last activity timestamp"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id]["last_activity"] = datetime.utcnow()
    
    async def increment_chunks(self, stream_id: str):
        """Increment chunks sent counter"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id]["chunks_sent"] += 1
    
    async def close_stream(self, stream_id: str):
        """Close and cleanup stream"""
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
        if stream_id in self.reconnect_attempts:
            del self.reconnect_attempts[stream_id]
    
    async def should_reconnect(self, stream_id: str) -> bool:
        """Check if should attempt reconnection"""
        attempts = self.reconnect_attempts.get(stream_id, 0)
        if attempts < self.max_reconnect_attempts:
            self.reconnect_attempts[stream_id] = attempts + 1
            return True
        return False
    
    async def get_backoff_delay(self, stream_id: str) -> float:
        """Calculate exponential backoff delay"""
        attempts = self.reconnect_attempts.get(stream_id, 0)
        return min(2 ** attempts, 16)  # Max 16 seconds


async def sse_generator(
    stream_id: str,
    content_generator: AsyncGenerator[str, None],
    stream_manager: StreamManager
) -> AsyncGenerator[str, None]:
    """
    Generate SSE format stream with error handling
    """
    try:
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'stream_id': stream_id})}\n\n"
        
        full_content = ""
        
        async for chunk in content_generator:
            try:
                # Update activity
                await stream_manager.update_activity(stream_id)
                await stream_manager.increment_chunks(stream_id)
                
                # Add to buffer
                chunk_data = {
                    "type": "content",
                    "data": chunk,
                    "stream_id": stream_id
                }
                await stream_manager.buffer.add(chunk_data)
                
                # Send SSE formatted chunk
                full_content += chunk
                yield f"event: message\ndata: {json.dumps(chunk_data)}\n\n"
                
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                error_data = {
                    "type": "error",
                    "data": str(e),
                    "stream_id": stream_id
                }
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        
        # Send completion event
        completion_data = {
            "type": "done",
            "data": full_content,
            "stream_id": stream_id
        }
        yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"
        
    except asyncio.CancelledError:
        logger.info(f"Stream {stream_id} cancelled")
        raise
    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        error_data = {
            "type": "error",
            "data": str(e),
            "stream_id": stream_id
        }
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    finally:
        await stream_manager.close_stream(stream_id)


async def heartbeat_generator(interval: int = 15) -> AsyncGenerator[str, None]:
    """
    Generate heartbeat pings to keep connection alive
    """
    while True:
        await asyncio.sleep(interval)
        yield f"event: ping\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"


async def merge_generators(*generators) -> AsyncGenerator[str, None]:
    """
    Merge multiple async generators into one
    """
    queue = asyncio.Queue()
    
    async def consume(gen):
        try:
            async for item in gen:
                await queue.put(item)
        except Exception as e:
            logger.error(f"Generator error: {str(e)}")
        finally:
            await queue.put(None)
    
    tasks = [asyncio.create_task(consume(gen)) for gen in generators]
    active_generators = len(generators)
    
    while active_generators > 0:
        item = await queue.get()
        if item is None:
            active_generators -= 1
        else:
            yield item
    
    for task in tasks:
        task.cancel()


# Global stream manager instance
stream_manager = StreamManager()