const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class StreamingService {
  constructor() {
    this.eventSource = null;
    this.websocket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.buffer = [];
    this.maxBufferSize = 1000;
  }

  /**
   * Start SSE stream
   */
  async startSSEStream(request, onMessage, onError, onComplete) {
    const token = localStorage.getItem('access_token');
    
    try {
      // Make POST request to get stream
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          onComplete('');
          break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              this.addToBuffer(data);
              
              if (data.type === 'content') {
                onMessage(data.data);
              } else if (data.type === 'done') {
                onComplete(data.data);
                return;
              } else if (data.type === 'error') {
                onError(data.data);
                return;
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to start SSE stream:', error);
      onError(error.message);
    }
  }

  /**
   * Fallback to WebSocket
   */
  async startWebSocketStream(request, onMessage, onError, onComplete) {
    const token = localStorage.getItem('access_token');
    const wsUrl = API_URL.replace('http', 'ws');

    try {
      this.websocket = new WebSocket(`${wsUrl}/api/chat/ws`);

      this.websocket.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        
        // Send request
        this.websocket.send(JSON.stringify({
          ...request,
          token
        }));
      };

      this.websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.addToBuffer(data);

          if (data.type === 'content') {
            onMessage(data.data);
          } else if (data.type === 'done') {
            onComplete(data.data);
            this.close();
          } else if (data.type === 'error') {
            onError(data.data);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError('WebSocket connection failed');
      };

      this.websocket.onclose = () => {
        console.log('WebSocket closed');
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnect(request, onMessage, onError, onComplete);
        }
      };

    } catch (error) {
      console.error('Failed to start WebSocket stream:', error);
      onError(error.message);
    }
  }

  /**
   * Reconnect with exponential backoff
   */
  async reconnect(request, onMessage, onError, onComplete) {
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 16000);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      if (this.eventSource) {
        this.startSSEStream(request, onMessage, onError, onComplete);
      } else if (this.websocket) {
        this.startWebSocketStream(request, onMessage, onError, onComplete);
      }
    }, delay);
  }

  /**
   * Add to circular buffer
   */
  addToBuffer(data) {
    this.buffer.push({
      ...data,
      timestamp: new Date().toISOString()
    });

    if (this.buffer.length > this.maxBufferSize) {
      this.buffer.shift();
    }
  }

  /**
   * Get recent buffer items
   */
  getRecentBuffer(n = 10) {
    return this.buffer.slice(-n);
  }

  /**
   * Close connection
   */
  close() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }

    this.reconnectAttempts = 0;
  }
}