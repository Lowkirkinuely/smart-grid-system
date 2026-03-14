/**
 * WebSocket Service for real-time grid state updates
 */

export interface WebSocketMessage {
  type: string;
  timestamp?: string;
  thread_id?: string;
  grid_state?: any;
  plans?: any[];
  ai_analysis?: any;
  requires_human_approval?: boolean;
  recommended_plan?: any;
  stage?: string;
  active_connections?: number;
  recent_updates?: any[];
  agent_name?: string;
  activity?: string;
  status?: string;
  message?: string;
  [key: string]: any; // Allow any additional properties for flexibility
}

export type WebSocketMessageHandler = (message: WebSocketMessage) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Map<string, Set<WebSocketMessageHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000;
  private isIntentionallyClosed = false;

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Subscribe to a specific message type
   */
  on(messageType: string, handler: WebSocketMessageHandler): () => void {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, new Set());
    }
    this.handlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(messageType)?.delete(handler);
    };
  }

  /**
   * Connect to WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log("[WebSocket] Connected");
          this.reconnectAttempts = 0;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            console.log(`[WebSocket] Received message type: ${message.type}`, message);
            this.emit(message.type, message);
          } catch (e) {
            console.error("[WebSocket] Failed to parse message:", e);
          }
        };

        this.ws.onerror = (error) => {
          console.error("[WebSocket] Error:", error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log("[WebSocket] Disconnected");
          if (!this.isIntentionallyClosed) {
            this.attemptReconnect();
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Send a message through WebSocket
   */
  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn("[WebSocket] Not connected, message not sent:", message);
    }
  }

  /**
   * Emit a message to all subscribers
   */
  private emit(messageType: string, message: WebSocketMessage): void {
    const handlers = this.handlers.get(messageType);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error(`[WebSocket] Error in handler for ${messageType}:`, error);
        }
      });
    }
  }

  /**
   * Attempt to reconnect
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(
        `[WebSocket] Reconnecting... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${this.reconnectDelay}ms`
      );
      setTimeout(() => {
        this.connect().catch((error) => {
          console.error("[WebSocket] Reconnection failed:", error);
        });
      }, this.reconnectDelay);
    } else {
      console.error("[WebSocket] Max reconnection attempts reached");
    }
  }

  /**
   * Close connection gracefully
   */
  close(): void {
    this.isIntentionallyClosed = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export default WebSocketService;
