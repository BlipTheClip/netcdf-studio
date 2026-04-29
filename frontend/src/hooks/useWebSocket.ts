import { useEffect, useRef, useState, useCallback } from "react";
import { createWsConnection } from "@/api/client";
import type { WsMessage, WsProgressPayload } from "@/api/types";

interface UseWebSocketOptions<TResult, TProgress extends WsProgressPayload> {
  onMessage?: (msg: WsMessage<TResult, TProgress>) => void;
}

interface UseWebSocketReturn {
  send: (data: unknown) => void;
  close: () => void;
  readyState: number;
  isOpen: boolean;
}

/**
 * React hook wrapping createWsConnection.
 *
 * Pass a non-null `endpoint` to open the connection; set it to null to keep
 * it closed. The connection is cleaned up automatically on unmount or when
 * the endpoint changes.
 *
 * The `onMessage` callback is stored in a ref so callers can pass an inline
 * function without causing unnecessary reconnects.
 */
export function useWebSocket<
  TResult,
  TProgress extends WsProgressPayload = WsProgressPayload,
>(
  endpoint: string | null,
  options: UseWebSocketOptions<TResult, TProgress> = {},
): UseWebSocketReturn {
  const handleRef = useRef<ReturnType<typeof createWsConnection> | null>(null);
  const [readyState, setReadyState] = useState<number>(WebSocket.CLOSED);

  // Keep callback stable across renders without triggering re-connections.
  const onMessageRef = useRef(options.onMessage);
  onMessageRef.current = options.onMessage;

  useEffect(() => {
    if (!endpoint) return;

    setReadyState(WebSocket.CONNECTING);

    const handle = createWsConnection<TResult, TProgress>(
      endpoint,
      (msg) => onMessageRef.current?.(msg),
      () => setReadyState(WebSocket.OPEN),
      () => setReadyState(WebSocket.CLOSED),
    );

    handleRef.current = handle;

    return () => {
      handle.close();
      handleRef.current = null;
    };
  }, [endpoint]);

  const send = useCallback((data: unknown) => {
    handleRef.current?.send(data);
  }, []);

  const close = useCallback(() => {
    handleRef.current?.close();
  }, []);

  return { send, close, readyState, isOpen: readyState === WebSocket.OPEN };
}
