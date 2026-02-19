import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Loader2, Bot, User } from "lucide-react";
import clsx from "clsx";
import type { ChatMessage } from "../api/types";

interface SecurityChatProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SecurityChat({ isOpen, onClose }: SecurityChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I'm your security assistant. I can help you:\n\n" +
        "- Analyze vulnerabilities\n" +
        "- Find remediation steps\n" +
        "- Query security posture\n" +
        "- Run security scans\n\n" +
        "What would you like to know?",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  async function handleSend() {
    const text = input.trim();
    if (!text) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    try {
      const response = await fetch("/api/v1/security/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token") ?? ""}`,
        },
        body: JSON.stringify({ message: text }),
      });

      if (response.ok) {
        const data = (await response.json()) as { response?: string; actions?: ChatMessage["actions"] };
        const assistantMessage: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response ?? "I encountered an error processing your request.",
          timestamp: new Date().toISOString(),
          actions: data.actions,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again.",
            timestamp: new Date().toISOString(),
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: "Connection error. Please check your network and try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed bottom-0 right-0 z-40 flex h-[600px] w-[420px] flex-col rounded-tl-xl border-l border-t border-gray-700 bg-gray-900 shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-brand-400" />
          <span className="text-sm font-semibold text-gray-100">Security Assistant</span>
        </div>
        <button onClick={onClose} className="rounded-lg p-1 hover:bg-gray-800">
          <X className="h-4 w-4 text-gray-400" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={clsx(
              "flex gap-2",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            {msg.role === "assistant" && (
              <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500/20">
                <Bot className="h-3.5 w-3.5 text-brand-400" />
              </div>
            )}
            <div
              className={clsx(
                "max-w-[300px] rounded-lg px-3 py-2 text-sm",
                msg.role === "user" ? "bg-brand-500 text-white" : "bg-gray-800 text-gray-200"
              )}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.actions && msg.actions.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {msg.actions.map((action, i) => (
                    <button
                      key={i}
                      className="rounded border border-brand-500/30 bg-brand-500/10 px-2 py-0.5 text-xs text-brand-300 hover:bg-brand-500/20"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {msg.role === "user" && (
              <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-700">
                <User className="h-3.5 w-3.5 text-gray-300" />
              </div>
            )}
          </div>
        ))}

        {isTyping && (
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500/20">
              <Bot className="h-3.5 w-3.5 text-brand-400" />
            </div>
            <div className="rounded-lg bg-gray-800 px-3 py-2">
              <div className="flex gap-1">
                <span
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 px-4 py-3">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about security..."
            className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:border-brand-500 focus:outline-none"
            disabled={isTyping}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            className="rounded-lg bg-brand-500 px-3 py-2 text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {isTyping ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Unused import retained for module completeness (icon used in parent callers)
export { MessageSquare };
