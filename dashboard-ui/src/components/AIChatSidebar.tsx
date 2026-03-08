import { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageSquare,
  X,
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  RotateCcw,
} from "lucide-react";
import clsx from "clsx";
import { post } from "../api/client";

// ── Types ────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatResponse {
  id: string;
  role: "assistant";
  content: string;
  timestamp: string;
}

// ── Suggested prompts ────────────────────────────────────────────

const SUGGESTIONS = [
  "What's my current security posture?",
  "Show me open critical vulnerabilities",
  "Summarize recent incidents",
  "What agents are running right now?",
];

// ── Component ────────────────────────────────────────────────────

export default function AIChatSidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsLoading(true);

      try {
        const response = await post<ChatResponse>("/security/chat", {
          message: content.trim(),
          context: {
            page: window.location.pathname,
            history: messages.slice(-6).map((m) => ({
              role: m.role,
              content: m.content,
            })),
          },
        });

        const assistantMsg: ChatMessage = {
          id: response.id,
          role: "assistant",
          content: response.content,
          timestamp: new Date(response.timestamp),
        };

        setMessages((prev) => [...prev, assistantMsg]);
      } catch {
        const errorMsg: ChatMessage = {
          id: `error-${Date.now()}`,
          role: "assistant",
          content:
            "Sorry, I couldn't process that request. Please try again.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, messages],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(input);
      }
    },
    [input, sendMessage],
  );

  const handleClear = useCallback(() => {
    setMessages([]);
  }, []);

  return (
    <>
      {/* FAB trigger */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-brand-500 text-white shadow-lg transition-all hover:bg-brand-600 hover:shadow-xl"
          aria-label="Open AI assistant"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
      )}

      {/* Chat panel */}
      <div
        className={clsx(
          "fixed bottom-0 right-0 z-50 flex h-[min(600px,85vh)] w-[380px] flex-col rounded-tl-xl border-l border-t border-gray-700 bg-gray-900 shadow-2xl transition-transform duration-300",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/20">
              <Sparkles className="h-4 w-4 text-brand-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-100">
                ShieldOps AI
              </h3>
              <p className="text-[10px] text-gray-500">Security assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={handleClear}
                className="rounded p-1.5 text-gray-500 hover:bg-gray-800 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                aria-label="Clear chat"
                title="Clear chat"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={() => setIsOpen(false)}
              className="rounded p-1.5 text-gray-500 hover:bg-gray-800 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
              aria-label="Close AI assistant"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4">
              <div className="rounded-full bg-brand-500/10 p-3">
                <Bot className="h-6 w-6 text-brand-400" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-gray-200">
                  How can I help?
                </p>
                <p className="mt-1 text-xs text-gray-500">
                  Ask about security, incidents, or operations
                </p>
              </div>
              <div className="mt-2 flex w-full flex-col gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => sendMessage(suggestion)}
                    className="rounded-lg border border-gray-800 px-3 py-2 text-left text-xs text-gray-400 transition-colors hover:border-gray-700 hover:bg-gray-800/50 hover:text-gray-300"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={clsx(
                    "flex gap-2.5",
                    msg.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  {msg.role === "assistant" && (
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand-500/20">
                      <Bot className="h-3.5 w-3.5 text-brand-400" />
                    </div>
                  )}
                  <div
                    className={clsx(
                      "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                      msg.role === "user"
                        ? "bg-brand-500 text-white"
                        : "bg-gray-800 text-gray-200",
                    )}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  {msg.role === "user" && (
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gray-700">
                      <User className="h-3.5 w-3.5 text-gray-300" />
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex items-center gap-2.5">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand-500/20">
                    <Bot className="h-3.5 w-3.5 text-brand-400" />
                  </div>
                  <div className="rounded-lg bg-gray-800 px-3 py-2">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-gray-800 p-3">
          <div className="flex items-end gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything..."
              rows={1}
              className="max-h-[80px] flex-1 resize-none bg-transparent text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none"
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading}
              className={clsx(
                "shrink-0 rounded-md p-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                input.trim() && !isLoading
                  ? "bg-brand-500 text-white hover:bg-brand-600"
                  : "text-gray-600",
              )}
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-1.5 text-center text-[10px] text-gray-600">
            AI can make mistakes. Verify important information.
          </p>
        </div>
      </div>
    </>
  );
}
