"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import type { LiveEventItem } from "@/types";

export type ConnectionState = "connecting" | "live" | "reconnecting" | "offline";

interface LiveMessage {
  kind: "event" | "alert";
  data: LiveEventItem | Record<string, unknown>;
}

interface LiveStreamContextValue {
  connection: ConnectionState;
  events: LiveEventItem[];
  lastEvent: LiveEventItem | null;
  lastAlert: (LiveEventItem & Record<string, unknown>) | null;
  clearEvents: () => void;
}

const LiveStreamContext = createContext<LiveStreamContextValue | null>(null);

const MAX_EVENTS = 200;

export function LiveStreamProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [events, setEvents] = useState<LiveEventItem[]>([]);
  const [lastEvent, setLastEvent] = useState<LiveEventItem | null>(null);
  const [lastAlert, setLastAlert] = useState<LiveEventItem & Record<string, unknown> | null>(null);
  const reconnectAttempt = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventsRef = useRef<LiveEventItem[]>([]);
  const tokenRef = useRef(token);
  tokenRef.current = token;

  const appendEvent = useCallback((event: LiveEventItem) => {
    eventsRef.current = [event, ...eventsRef.current].slice(0, MAX_EVENTS);
    setEvents(eventsRef.current);
    setLastEvent(event);
  }, []);

  const scheduleReconnect = useCallback((attempt: number) => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    const delay = Math.min(1000 * 2 ** attempt, 15000);
    reconnectTimerRef.current = setTimeout(() => connectRef.current(), delay);
  }, []);

  const connect = useCallback(() => {
    const authToken = tokenRef.current;
    if (!authToken) {
      setConnection("offline");
      return;
    }
    const controller = new AbortController();
    controllerRef.current = controller;
    setConnection("connecting");

    const url = `${API_URL}/api/stream/live`;
    const run = async () => {
      try {
        const response = await fetch(url, {
          headers: {
            Accept: "text/event-stream",
            Authorization: `Bearer ${authToken}`,
          },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          throw new Error(`Stream failed: ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        setConnection("live");
        reconnectAttempt.current = 0;

        if (eventsRef.current.length === 0) {
          try {
            const recent = await fetch(`${API_URL}/api/dashboard/live-events?limit=20`, {
              headers: { Authorization: `Bearer ${authToken}` },
            });
            if (recent.ok) {
              const items = (await recent.json()) as LiveEventItem[];
              if (items.length > 0 && eventsRef.current.length === 0) {
                eventsRef.current = items;
                setEvents(items);
              }
            }
          } catch {
            /* recent-events prefill is best-effort */
          }
        }

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() ?? "";
          for (const chunk of lines) {
            for (const line of chunk.split("\n")) {
              if (!line.startsWith("data:")) continue;
              const raw = line.slice(5).trim();
              try {
                const message = JSON.parse(raw) as LiveMessage;
                if (message.kind === "event" && message.data && "event_id" in message.data) {
                  appendEvent(message.data as LiveEventItem);
                } else if (message.kind === "alert") {
                  setLastAlert(message.data as LiveEventItem & Record<string, unknown>);
                }
              } catch {
                /* malformed frame, ignore */
              }
            }
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setConnection("reconnecting");
        const attempt = reconnectAttempt.current;
        reconnectAttempt.current += 1;
        scheduleReconnect(attempt);
      }
    };
    void run();

    return () => {
      controller.abort();
    };
  }, [appendEvent, scheduleReconnect]);

  const connectRef = useRef(connect);
  connectRef.current = connect;

  useEffect(() => {
    const cleanup = connect();
    return () => {
      cleanup?.();
      controllerRef.current?.abort();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [connect, token]);

  const value = useMemo<LiveStreamContextValue>(
    () => ({
      connection,
      events,
      lastEvent,
      lastAlert,
      clearEvents: () => {
        eventsRef.current = [];
        setEvents([]);
      },
    }),
    [connection, events, lastEvent, lastAlert],
  );

  return <LiveStreamContext.Provider value={value}>{children}</LiveStreamContext.Provider>;
}

export function useLiveStream(): LiveStreamContextValue {
  const ctx = useContext(LiveStreamContext);
  if (!ctx) throw new Error("useLiveStream must be used within LiveStreamProvider");
  return ctx;
}
