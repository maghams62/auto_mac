"use client";

import React, { memo } from "react";
import { Message } from "@/lib/useWebSocket";
import { cn } from "@/lib/utils";

interface BlueskyNotificationCardProps {
  notification: NonNullable<Message["bluesky_notification"]>;
  onAction?: (action: string, uri: string, url?: string) => void;
}

const BlueskyNotificationCard = memo<BlueskyNotificationCardProps>(
  ({ notification, onAction }) => {
    const handleAction = (action: string) => {
      if (onAction) {
        const uri = notification.uri || (notification.post?.uri) || "";
        let url = "";

        // Get the correct URL for opening
        if (notification.source === "notification" && notification.subject_post?.url) {
          url = notification.subject_post.url;
        } else if (notification.source === "timeline_mention" && notification.post?.url) {
          url = notification.post.url;
        }

        onAction(action, uri, url);
      }
    };

    const isNotification = notification.source === "notification";
    const isTimelineMention = notification.source === "timeline_mention";

    return (
      <div className="mt-3 p-4 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-blue-500/10 border border-blue-500/20 rounded-lg">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-medium text-blue-400">
                {isNotification ? "🔔" : "💬"}
              </span>
              <span className="text-sm font-medium text-blue-300">
                @{notification.author_handle}
              </span>
              <span className="text-xs text-blue-400/70">
                {notification.author_name}
              </span>
            </div>

            {isNotification && notification.subject_post && (
              <div className="mb-3 p-3 bg-white/5 rounded border border-white/10">
                <p className="text-sm text-white/80 line-clamp-3">
                  &ldquo;{notification.subject_post.text}&rdquo;
                </p>
              </div>
            )}

            {isTimelineMention && notification.post && (
              <div className="mb-3">
                <p className="text-sm text-white/80 line-clamp-3">
                  &ldquo;{notification.post.text}&rdquo;
                </p>
              </div>
            )}

            <div className="flex items-center gap-2 text-xs text-blue-400/70">
              <span>
                {isNotification
                  ? `${notification.reason || notification.notification_type || "notification"}`
                  : "mentioned you"
                }
              </span>
              <span>•</span>
              <span>
                {new Date(notification.timestamp).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </span>
            </div>
          </div>

          <div className="flex gap-1 ml-4">
            {/* Open button - only show if we have a URL */}
            {((notification.source === "notification" && notification.subject_post?.url) ||
              (notification.source === "timeline_mention" && notification.post?.url)) && (
              <button
                onClick={() => handleAction("open")}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded transition-colors",
                  "bg-white/10 hover:bg-white/20 text-white/80 hover:text-white",
                  "border border-white/20 hover:border-white/30"
                )}
              >
                Open
              </button>
            )}

            {/* Action buttons - only show if we have a URI */}
            {notification.uri && (
              <>
                <button
                  onClick={() => handleAction("reply")}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded transition-colors",
                    "bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 hover:text-blue-200",
                    "border border-blue-500/30 hover:border-blue-500/40"
                  )}
                >
                  Reply
                </button>

                <button
                  onClick={() => handleAction("like")}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded transition-colors",
                    "bg-pink-500/20 hover:bg-pink-500/30 text-pink-300 hover:text-pink-200",
                    "border border-pink-500/30 hover:border-pink-500/40"
                  )}
                >
                  Like
                </button>

                <button
                  onClick={() => handleAction("repost")}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded transition-colors",
                    "bg-green-500/20 hover:bg-green-500/30 text-green-300 hover:text-green-200",
                    "border border-green-500/30 hover:border-green-500/40"
                  )}
                >
                  Repost
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }
);

BlueskyNotificationCard.displayName = "BlueskyNotificationCard";

export default BlueskyNotificationCard;
