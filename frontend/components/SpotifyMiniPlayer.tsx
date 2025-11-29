"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getApiBaseUrl } from "@/lib/apiConfig";
import logger from "@/lib/logger";
import { useGlobalEventBus } from "@/lib/telemetry";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";

interface SpotifyMiniPlayerProps {
  variant?: "launcher" | "palette-row" | "launcher-footer" | "launcher-full" | "launcher-expanded" | "launcher-mini";
  onAction?: () => void; // Called when user interacts (for hiding launcher)
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

// Format milliseconds to mm:ss
function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

interface SpotifyStatus {
  is_playing: boolean;
  item?: {
    name: string;
    artists: Array<{ name: string }>;
    album: {
      name: string;
      images: Array<{ url: string }>;
    };
    duration_ms: number;
    uri?: string;
    id?: string;
  };
  progress_ms: number;
  device?: {
    name: string;
    type: string;
  };
}

type SpotifyVariant = SpotifyMiniPlayerProps["variant"];
const DEFAULT_ALBUM_ART = "/spotify-placeholder.svg";
const SKELETON_VARIANTS = new Set<SpotifyVariant>([
  "launcher",
  "launcher-full",
  "launcher-footer",
  "launcher-expanded",
  "launcher-mini",
]);
const SPOTIFY_EMBED_BASE_URL = "https://open.spotify.com/embed";

function buildSpotifyEmbedUrl(uri?: string): string | null {
  if (!uri) {
    return null;
  }

  const segments = uri.split(':');
  if (segments.length < 3) {
    return null;
  }

  const [, resourceType, ...rest] = segments;
  const resourceId = rest.join(':');

  if (!resourceType || !resourceId) {
    return null;
  }

  const encodedType = encodeURIComponent(resourceType);
  const encodedId = encodeURIComponent(resourceId);

  return `${SPOTIFY_EMBED_BASE_URL}/${encodedType}/${encodedId}?utm_source=cerebro&theme=0`;
}

function SpotifySkeleton({ variant, collapsed }: { variant: SpotifyVariant; collapsed?: boolean }) {
  if (variant === "launcher-expanded") {
    return (
      <motion.div
        className="w-full bg-gradient-to-b from-[#1a1a1a] to-[#121212] rounded-xl overflow-hidden"
        initial={{ opacity: 0.4, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#1DB954] animate-pulse" />
            <div className="h-4 w-16 rounded-full bg-white/10" />
          </div>
          <div className="h-4 w-20 rounded-full bg-white/10" />
        </div>
        {!collapsed ? (
          <div className="px-6 pb-6 space-y-5">
            <div className="flex justify-center">
              <div className="w-56 h-56 rounded-xl bg-white/5 animate-pulse" />
            </div>
            <div className="space-y-2 text-center">
              <div className="h-5 w-40 bg-white/10 rounded-full mx-auto" />
              <div className="h-4 w-32 bg-white/5 rounded-full mx-auto" />
            </div>
            <div className="space-y-2">
              <div className="h-1.5 rounded-full bg-white/10" />
              <div className="flex justify-between text-xs text-white/50">
                <div className="h-3 w-10 rounded-full bg-white/10" />
                <div className="h-3 w-10 rounded-full bg-white/10" />
              </div>
            </div>
            <div className="flex items-center justify-center gap-6">
              <div className="w-10 h-10 rounded-full bg-white/10" />
              <div className="w-16 h-16 rounded-full bg-white/10" />
              <div className="w-10 h-10 rounded-full bg-white/10" />
            </div>
          </div>
        ) : (
          <div className="px-4 pb-3 space-y-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded bg-white/10 animate-pulse" />
              <div className="flex-1 space-y-1">
                <div className="h-4 w-32 bg-white/10 rounded-full" />
                <div className="h-3 w-20 bg-white/5 rounded-full" />
              </div>
              <div className="w-8 h-8 rounded-full bg-white/10" />
            </div>
            <div className="h-1 bg-white/10 rounded-full" />
          </div>
        )}
      </motion.div>
    );
  }

  if (variant === "launcher-full") {
    return (
      <div
        className="w-full px-4 py-4 bg-gradient-to-r from-[#1DB954]/10 via-glass/20 to-glass/10 border-t border-[#1DB954]/20 rounded-xl animate-pulse"
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-lg bg-white/10" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-40 bg-white/10 rounded-full" />
            <div className="h-3 w-32 bg-white/5 rounded-full" />
            <div className="h-3 w-24 bg-[#1DB954]/20 rounded-full" />
          </div>
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-full bg-white/10" />
            <div className="w-12 h-12 rounded-full bg-[#1DB954]/30" />
            <div className="w-9 h-9 rounded-full bg-white/10" />
          </div>
        </div>
        <div className="mt-3 h-1.5 bg-white/10 rounded-full" />
      </div>
    );
  }

  if (variant === "launcher" || variant === "launcher-footer") {
    return (
      <div
        className="w-full px-4 py-3 border-t border-glass/30 bg-glass/20 backdrop-blur-xl rounded-xl animate-pulse"
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-white/10" />
          <div className="flex-1 space-y-1">
            <div className="h-4 w-40 bg-white/10 rounded-full" />
            <div className="h-3 w-28 bg-white/5 rounded-full" />
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-white/10" />
            <div className="w-8 h-8 rounded-full bg-white/10" />
            <div className="w-8 h-8 rounded-full bg-white/10" />
          </div>
        </div>
      </div>
    );
  }

  // Launcher mini variant skeleton - horizontal compact
  if (variant === "launcher-mini") {
    return (
      <motion.div
        className="w-[320px] bg-black/95 backdrop-blur-xl rounded-xl shadow-2xl overflow-hidden"
        initial={{ opacity: 0.4, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex items-center gap-3 p-3">
          {/* Album art skeleton */}
          <div className="w-12 h-12 rounded-md bg-white/10 animate-pulse flex-shrink-0" />

          {/* Track info skeleton */}
          <div className="flex-1 min-w-0 space-y-2">
            <div className="h-3.5 w-32 bg-white/10 rounded-full animate-pulse" />
            <div className="h-3 w-24 bg-white/5 rounded-full animate-pulse" />
          </div>

          {/* Controls skeleton */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="w-4 h-4 rounded bg-white/10 animate-pulse" />
            <div className="w-8 h-8 rounded-full bg-white/10 animate-pulse" />
            <div className="w-4 h-4 rounded bg-white/10 animate-pulse" />
          </div>
        </div>
        <div className="px-4 pb-4">
          <div className="mt-1.5 h-1 bg-white/20 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-[#1DB954] rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </motion.div>
    );
  }

  return null;
}

export default function SpotifyMiniPlayer({
  variant = "launcher",
  onAction,
  collapsed = false,
  onToggleCollapse
}: SpotifyMiniPlayerProps) {
  const isElectronRuntime = useIsElectronRuntime();
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [lastKnownTrack, setLastKnownTrack] = useState<SpotifyStatus["item"] | null>(null);
  const [lastKnownStatus, setLastKnownStatus] = useState<SpotifyStatus | null>(null);
  const [missingItemCount, setMissingItemCount] = useState(0);
  const apiBaseUrl = getApiBaseUrl();
  const eventBus = useGlobalEventBus();

  // Log when component mounts
  useEffect(() => {
    logger.info(`[SPOTIFY-MINI-PLAYER] Component mounted with variant: ${variant}`);
  }, [variant]);

  // Fetch Spotify status
  const fetchStatus = useCallback(async () => {
    logger.debug(`[SPOTIFY-MINI-PLAYER] Fetching status from ${apiBaseUrl}/api/spotify/status`);
    try {
      const response = await fetch(`${apiBaseUrl}/api/spotify/status`);
      logger.debug(`[SPOTIFY-MINI-PLAYER] Status response: ${response.status}`);

      if (response.ok) {
        const data = await response.json();
        // API returns {"status": {...}}, unwrap it
        const statusData = data.status || data;
        logger.info(`[SPOTIFY-MINI-PLAYER] Status received:`, {
          hasItem: !!statusData.item,
          isPlaying: statusData.is_playing,
          track: statusData.item?.name,
          artist: statusData.item?.artists?.[0]?.name
        });
        setStatus(statusData);
        if (statusData.item) {
          setLastKnownTrack(statusData.item);
          setLastKnownStatus(statusData);
          setMissingItemCount(0);
        } else {
          setMissingItemCount(prev => Math.min(prev + 1, 5));
        }
        setIsAuthenticated(true);
      } else if (response.status === 401) {
        logger.warn(`[SPOTIFY-MINI-PLAYER] Not authenticated (401)`);
        setIsAuthenticated(false);
        setStatus(null);
        setLastKnownTrack(null);
        setLastKnownStatus(null);
        setMissingItemCount(0);
      }
    } catch (error) {
      logger.error("[SPOTIFY-MINI-PLAYER] Failed to fetch Spotify status:", error);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  // Dynamic polling - faster when playing, slower when idle
  // 1 second when playing for real-time progress, 3 seconds when idle
  const pollInterval = status?.is_playing ? 1000 : 3000;
  
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, pollInterval]);

  // Listen for spotify events from chat commands to refresh immediately
  useEffect(() => {
    const handleSpotifyUpdate = () => {
      // Refresh after short delay to allow Spotify API to update
      setTimeout(fetchStatus, 300);
      setTimeout(fetchStatus, 1000); // Double-check after 1s
      setTimeout(fetchStatus, 2000); // Triple-check after 2s for slow API responses
    };
    
    // Listen for any spotify control events from eventBus
    const unsubControl = eventBus.subscribe('spotify:control', handleSpotifyUpdate);
    const unsubPlayback = eventBus.subscribe('spotify:playback_started', handleSpotifyUpdate);
    
    // Listen for WebSocket playback updates (from backend broadcasts)
    const handleWebSocketUpdate = (event: CustomEvent) => {
      console.log('[SPOTIFY] WebSocket playback update received:', event.detail);
      handleSpotifyUpdate();
    };
    window.addEventListener('spotify:playback_update', handleWebSocketUpdate as EventListener);
    
    return () => {
      unsubControl();
      unsubPlayback();
      window.removeEventListener('spotify:playback_update', handleWebSocketUpdate as EventListener);
    };
  }, [fetchStatus, eventBus]);

  // Spotify controls - Note: We intentionally DON'T call onAction() here
  // to keep the launcher window open during Spotify interaction
  const handlePlayPause = useCallback(async () => {
    const action = status?.is_playing ? 'pause' : 'play';
    const trackName = status?.item?.name || 'unknown';
    logger.info(`[SPOTIFY] ${action.toUpperCase()} requested`, { track: trackName });
    
    // Emit telemetry event
    eventBus.emit('spotify:control', {
      action,
      track: trackName,
      source: 'button',
      timestamp: Date.now()
    });
    
    try {
      const endpoint = status?.is_playing ? 'pause' : 'play';
      await fetch(`${apiBaseUrl}/api/spotify/${endpoint}`, { method: 'POST' });
      await fetchStatus();
      logger.info(`[SPOTIFY] ${action} successful`, { track: trackName });
    } catch (error) {
      logger.error("[SPOTIFY] play/pause failed", { error, action });
    }
  }, [apiBaseUrl, status?.is_playing, status?.item?.name, fetchStatus, eventBus]);

  const handleNext = useCallback(async () => {
    const currentTrack = status?.item?.name || 'unknown';
    logger.info("[SPOTIFY] NEXT track requested", { currentTrack });
    
    // Emit telemetry event
    eventBus.emit('spotify:control', {
      action: 'next',
      track: currentTrack,
      source: 'button',
      timestamp: Date.now()
    });
    
    try {
      await fetch(`${apiBaseUrl}/api/spotify/next`, { method: 'POST' });
      setTimeout(fetchStatus, 500); // Small delay for Spotify API
      logger.info("[SPOTIFY] Next track successful");
    } catch (error) {
      logger.error("[SPOTIFY] Next track failed", { error });
    }
  }, [apiBaseUrl, fetchStatus, status?.item?.name, eventBus]);

  const handlePrevious = useCallback(async () => {
    const currentTrack = status?.item?.name || 'unknown';
    logger.info("[SPOTIFY] PREVIOUS track requested", { currentTrack });
    
    // Emit telemetry event
    eventBus.emit('spotify:control', {
      action: 'previous',
      track: currentTrack,
      source: 'button',
      timestamp: Date.now()
    });
    
    try {
      await fetch(`${apiBaseUrl}/api/spotify/previous`, { method: 'POST' });
      setTimeout(fetchStatus, 500);
      logger.info("[SPOTIFY] Previous track successful");
    } catch (error) {
      logger.error("[SPOTIFY] Previous track failed", { error });
    }
  }, [apiBaseUrl, fetchStatus, status?.item?.name, eventBus]);

  const handleLogin = useCallback(() => {
    window.open(`${apiBaseUrl}/api/spotify/login`, '_blank');
  }, [apiBaseUrl]);

  if (isLoading && SKELETON_VARIANTS.has(variant)) {
    logger.info(`[SPOTIFY-MINI-PLAYER] Rendering skeleton for variant: ${variant}`);
    return <SpotifySkeleton variant={variant} collapsed={collapsed} />;
  }

  if (isLoading) {
    logger.info(`[SPOTIFY-MINI-PLAYER] Still loading, returning null for variant: ${variant}`);
    return null;
  }

  // Not authenticated
  if (!isAuthenticated) {
    logger.warn(`[SPOTIFY-MINI-PLAYER] Not authenticated, variant: ${variant}`);
    if (variant === "palette-row") return null; // Don't show in palette if not authenticated
    if (variant === "launcher-mini") {
      return (
        <div className="w-full bg-gradient-to-r from-[#1a1a1a] to-[#121212] rounded-xl overflow-hidden px-4 py-3">
          <button
            onClick={handleLogin}
            className="w-full px-3 py-2 text-sm rounded-lg bg-[#1DB954] hover:bg-[#1ed760] text-white transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
            </svg>
            <span>Connect Spotify</span>
          </button>
        </div>
      );
    }
    if (variant === "launcher-footer") {
      return (
        <div className="w-full px-4 py-2 bg-glass/10">
          <button
            onClick={handleLogin}
            className="w-full px-3 py-2 text-sm rounded-lg bg-[#1DB954] hover:bg-[#1ed760] text-white transition-colors flex items-center justify-center gap-2"
          >
            <span>🎵</span>
            <span>Connect Spotify</span>
          </button>
        </div>
      );
    }

    return (
      <div className="w-full px-4 py-2 border-t border-glass/30 bg-glass/20">
        <button
          onClick={handleLogin}
          className="w-full px-3 py-2 text-sm rounded-lg bg-[#1DB954] hover:bg-[#1ed760] text-white transition-colors flex items-center justify-center gap-2"
        >
          <span>🎵</span>
          <span>Connect Spotify</span>
        </button>
      </div>
    );
  }

  const shouldUseFallbackTrack = !status?.item && !!lastKnownTrack && missingItemCount < 3;
  const trackCandidate = status?.item ?? (shouldUseFallbackTrack ? lastKnownTrack : null);
  const playbackStatus = (status?.item ? status : (shouldUseFallbackTrack ? lastKnownStatus : status)) ?? lastKnownStatus ?? status;

  // No active playback
  if (!trackCandidate || !playbackStatus) {
    logger.info(`[SPOTIFY-MINI-PLAYER] No active playback (status.item is null), variant: ${variant}`);
    if (variant === "palette-row") return null;
    if (variant === "launcher-mini") {
      logger.info(`[SPOTIFY-MINI-PLAYER] Rendering "Nothing playing" state for launcher-mini`);
      return (
        <motion.div
          className="w-[320px] bg-black/95 backdrop-blur-xl rounded-xl shadow-2xl overflow-hidden"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div className="flex items-center gap-3 p-3">
            <div className="w-12 h-12 rounded-md bg-white/10 flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-[#1DB954]" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Spotify</div>
              <div className="text-white/50 text-xs">Nothing playing</div>
            </div>
          </div>
        </motion.div>
      );
    }
    if (variant === "launcher-footer") {
      return (
        <div className="w-full px-4 py-2 bg-glass/10">
          <div className="flex items-center gap-3 text-sm text-muted">
            <span className="text-lg">🎵</span>
            <span>Spotify idle</span>
          </div>
        </div>
      );
    }

    return (
      <div className="w-full px-4 py-2 border-t border-glass/30 bg-glass/20">
        <div className="flex items-center gap-3 text-sm text-muted">
          <span className="text-lg">🎵</span>
          <span>Spotify idle</span>
        </div>
      </div>
    );
  }

  const track = trackCandidate;
  const progressMs = playbackStatus.progress_ms ?? 0;
  const progress = Math.min((progressMs / Math.max(track.duration_ms, 1)) * 100, 100);
  const albumImages = track.album?.images ?? [];
  const albumLargeImage = albumImages[0]?.url || albumImages[1]?.url || albumImages[2]?.url || DEFAULT_ALBUM_ART;
  const albumMediumImage = albumImages[1]?.url || albumImages[0]?.url || albumImages[2]?.url || DEFAULT_ALBUM_ART;
  const albumSmallImage = albumImages[2]?.url || albumImages[1]?.url || albumImages[0]?.url || DEFAULT_ALBUM_ART;
  const albumArtKey = `${track.name}-${track.album?.name ?? ""}-${track.artists.map(a => a.name).join(",")}`;

  logger.info(`[SPOTIFY-MINI-PLAYER] Rendering player with track data for variant: ${variant}`, {
    trackName: track.name,
    artist: track.artists?.[0]?.name,
  isPlaying: playbackStatus.is_playing,
    progress: progress.toFixed(1) + '%'
  });

  // Expanded launcher variant - matches Raycast/iOS style with large centered artwork
  if (variant === "launcher-expanded") {
    return (
      <motion.div 
        className="w-full bg-gradient-to-b from-[#1a1a1a] to-[#121212] rounded-xl overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        {/* Header - Spotify branding with collapse toggle */}
        <div 
          className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-white/5 transition-colors"
          onClick={onToggleCollapse}
        >
          <div className="flex items-center gap-3">
            {/* Spotify green dot indicator */}
            <div className="w-2 h-2 rounded-full bg-[#1DB954]" />
            {/* Spotify Logo */}
            <svg className="w-5 h-5 text-[#1DB954]" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
            </svg>
            <span className="text-sm font-medium text-white">Spotify</span>
          </div>
          <div className="flex items-center gap-2">
            {playbackStatus.device && (
              <span className="text-xs text-white/50 truncate max-w-[150px]">
                Playing on {playbackStatus.device.name}
              </span>
            )}
            <motion.svg 
              className="w-4 h-4 text-white/50"
              animate={{ rotate: collapsed ? 0 : 180 }}
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </motion.svg>
          </div>
        </div>

        {/* Collapsible content */}
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-6 pb-6">
                {/* Large centered album artwork */}
                <div className="flex justify-center mb-5">
                  <motion.div
                    className="relative"
                    whileHover={{ scale: 1.02, transition: { duration: 0.2 } }}
                    animate={playbackStatus.is_playing ? { rotate: [-0.25, 0.25, -0.25] } : { rotate: 0 }}
                    transition={playbackStatus.is_playing ? { duration: 8, repeat: Infinity, ease: "easeInOut" } : { duration: 0.4 }}
                  >
                    <motion.img
                      key={albumArtKey}
                      src={albumLargeImage}
                      alt={track.album.name}
                      loading="lazy"
                      className="w-56 h-56 rounded-xl shadow-2xl object-cover"
                      initial={{ opacity: 0.7, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.25 }}
                    />
                    {/* Album name overlay at bottom */}
                    <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent rounded-b-xl">
                      <p className="text-sm text-white/70 font-medium truncate text-center">
                        {track.album.name}
                      </p>
                    </div>
                  </motion.div>
                </div>

                {/* Track info - centered */}
                <div className="text-center mb-5">
                  <h3 className="text-xl font-bold text-[#1DB954] truncate mb-1">
                    {track.name}
                  </h3>
                  <p className="text-base text-white truncate">
                    {track.artists.map(a => a.name).join(", ")}
                  </p>
                  <p className="text-sm text-white/50 truncate mt-0.5">
                    {track.album.name}
                  </p>
                </div>

                {/* Progress bar with time */}
                <div className="mb-5">
                  <div className="h-1.5 bg-white/20 rounded-full overflow-hidden mb-2">
                    <motion.div
                      className="h-full bg-[#1DB954] rounded-full"
                      initial={{ width: `${progress}%` }}
                      animate={{ width: `${progress}%` }}
                      transition={{ duration: 1, ease: "linear" }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-white/50 font-mono">
                    <span>{formatTime(playbackStatus.progress_ms)}</span>
                    <span>{formatTime(track.duration_ms)}</span>
                  </div>
                </div>

                {/* Playback controls - centered with large play button */}
                <div className="flex items-center justify-center gap-8">
                  {/* Previous */}
                  <motion.button
                    onClick={handlePrevious}
                    className="p-2 text-white/70 hover:text-white transition-colors"
                    title="Previous"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
                    </svg>
                  </motion.button>

                  {/* Play/Pause - Large circular button */}
                  <motion.button
                    onClick={handlePlayPause}
                    className="w-16 h-16 rounded-full bg-white flex items-center justify-center shadow-xl"
                    title={playbackStatus.is_playing ? "Pause" : "Play"}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    {playbackStatus.is_playing ? (
                      <svg className="w-7 h-7 text-black" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                      </svg>
                    ) : (
                      <svg className="w-7 h-7 text-black ml-1" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                    )}
                  </motion.button>

                  {/* Next */}
                  <motion.button
                    onClick={handleNext}
                    className="p-2 text-white/70 hover:text-white transition-colors"
                    title="Next"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
                    </svg>
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapsed state - mini bar */}
        {collapsed && (
          <motion.div 
            className="px-4 pb-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="flex items-center gap-3">
              <motion.img
                key={`${albumArtKey}-collapsed`}
                src={albumSmallImage}
                alt={track.album.name}
                loading="lazy"
                className="w-10 h-10 rounded shadow object-cover"
                initial={{ opacity: 0.7 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white truncate">{track.name}</div>
                <div className="text-xs text-white/50 truncate">
                  {track.artists.map(a => a.name).join(", ")}
                </div>
              </div>
                  <motion.button
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePlayPause();
                    }}
                    className="w-8 h-8 rounded-full bg-white flex items-center justify-center"
                    whileTap={{ scale: 0.95 }}
                  >
                    {playbackStatus.is_playing ? (
                      <svg className="w-4 h-4 text-black" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-black ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                    )}
                  </motion.button>
            </div>
            {/* Mini progress bar */}
            <div className="mt-2 h-1 bg-white/20 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-[#1DB954] rounded-full"
                style={{ width: `${progress}%` }}
              />
            </div>
          </motion.div>
        )}
      </motion.div>
    );
  }

  // Launcher mini variant - use embedded Spotify player when available
  if (variant === "launcher-mini") {
    const embedSrc = isElectronRuntime && isAuthenticated ? buildSpotifyEmbedUrl(track.uri) : null;

    if (embedSrc) {
      return (
        <motion.div
          className="relative w-full rounded-2xl overflow-hidden border border-white/15 bg-black/60 backdrop-blur-2xl shadow-2xl"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <webview
            key={embedSrc}
            src={embedSrc}
            allowpopups="true"
            partition="persist:spotifyEmbed"
            className="h-[152px] w-full border-0"
            style={{ backgroundColor: "transparent" }}
          />
          <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-white/5" />
        </motion.div>
      );
    }

    return (
      <motion.div
        className="relative w-full min-h-[84px] bg-black/95 backdrop-blur-xl rounded-2xl shadow-2xl overflow-hidden"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        {/* Main content - horizontal layout */}
        <div className="flex items-center gap-3 p-4">
          {/* Album Art - Small square */}
          <motion.img
            key={`${albumArtKey}-mini`}
            src={albumSmallImage}
            alt={track.album.name}
            loading="lazy"
            className="w-14 h-14 rounded-lg object-cover flex-shrink-0"
            initial={{ opacity: 0.7, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
          />

          {/* Track Info - flexible width */}
          <div className="flex-1 min-w-0">
            <h3 className="text-white font-medium text-sm leading-tight truncate">
              {track.name}
            </h3>
            <p className="text-white/50 text-xs truncate">
              {track.artists.map(a => a.name).join(", ")}
            </p>
          </div>

          {/* Playback Controls - compact row */}
          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Previous */}
            <motion.button
              onClick={handlePrevious}
              className="text-white/60 hover:text-white transition-colors"
              title="Previous"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
              </svg>
            </motion.button>

            {/* Play/Pause */}
            <motion.button
              onClick={handlePlayPause}
              className="bg-white text-black rounded-full w-9 h-9 flex items-center justify-center shadow-md hover:scale-105 transition-transform"
              title={playbackStatus.is_playing ? "Pause" : "Play"}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              {playbackStatus.is_playing ? (
                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              )}
            </motion.button>

            {/* Next */}
            <motion.button
              onClick={handleNext}
              className="text-white/60 hover:text-white transition-colors"
              title="Next"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
              </svg>
            </motion.button>
          </div>
        </div>
      </motion.div>
    );
  }

  // Full launcher variant - larger with time display (like Web SDK)
  if (variant === "launcher-full") {
    return (
      <div className="w-full px-4 py-4 bg-gradient-to-r from-[#1DB954]/10 via-glass/20 to-glass/10 border-t border-[#1DB954]/20">
        <div className="flex items-center gap-4">
          {/* Large Album art with shadow */}
          <div className="relative">
            <motion.img
              key={`${albumArtKey}-full`}
              src={albumMediumImage}
              alt={track.album.name}
              loading="lazy"
              className="w-16 h-16 rounded-lg shadow-lg object-cover"
              initial={{ opacity: 0.7, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2 }}
            />
            {playbackStatus.is_playing && (
              <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-[#1DB954] rounded-full flex items-center justify-center">
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="w-2 h-2 bg-white rounded-full"
                />
              </div>
            )}
          </div>

          {/* Track info */}
          <div className="flex-1 min-w-0">
            <div className="text-base font-semibold text-text-primary truncate">{track.name}</div>
            <div className="text-sm text-text-muted truncate">
              {track.artists.map(a => a.name).join(", ")}
            </div>
            <div className="text-xs text-[#1DB954] mt-1">
              {track.album.name}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <motion.button
              onClick={handlePrevious}
              className="p-2.5 rounded-full hover:bg-glass-hover transition-all"
              title="Previous"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
              </svg>
            </motion.button>
            <motion.button
              onClick={handlePlayPause}
              className="p-3 rounded-full bg-[#1DB954] hover:bg-[#1ed760] text-white shadow-lg transition-all"
              title={playbackStatus.is_playing ? "Pause" : "Play"}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              {playbackStatus.is_playing ? (
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
              ) : (
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              )}
            </motion.button>
            <motion.button
              onClick={handleNext}
              className="p-2.5 rounded-full hover:bg-glass-hover transition-all"
              title="Next"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
              </svg>
            </motion.button>
          </div>
        </div>

        {/* Progress bar with time */}
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-text-muted w-10 text-right font-mono">
            {formatTime(playbackStatus.progress_ms)}
          </span>
          <div className="flex-1 h-1.5 bg-glass/30 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-[#1DB954] rounded-full"
              initial={{ width: `${progress}%` }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 1, ease: "linear" }}
            />
          </div>
          <span className="text-xs text-text-muted w-10 font-mono">
            {formatTime(track.duration_ms)}
          </span>
        </div>

        {/* Device indicator */}
        {playbackStatus.device && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-[#1DB954]">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
            </svg>
            <span>{playbackStatus.device.name}</span>
          </div>
        )}
      </div>
    );
  }

  // Launcher footer variant (embedded at bottom of launcher)
  if (variant === "launcher-footer") {
    return (
      <div className="w-full px-4 py-3 bg-glass/10">
        <div className="flex items-center gap-3">
          {/* Album art */}
          <img
            src={albumSmallImage}
            alt={track.album.name}
            loading="lazy"
            className="w-10 h-10 rounded shadow-md object-cover"
          />

          {/* Track info */}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{track.name}</div>
            <div className="text-xs text-muted truncate">
              {track.artists.map(a => a.name).join(", ")}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={handlePrevious}
              className="p-1.5 rounded hover:bg-glass-hover transition-colors"
              title="Previous"
            >
              <span className="text-sm">⏮</span>
            </button>
            <button
              onClick={handlePlayPause}
              className="p-1.5 rounded hover:bg-glass-hover transition-colors"
              title={playbackStatus.is_playing ? "Pause" : "Play"}
            >
              <span className="text-sm">{playbackStatus.is_playing ? "⏸" : "▶️"}</span>
            </button>
            <button
              onClick={handleNext}
              className="p-1.5 rounded hover:bg-glass-hover transition-colors"
              title="Next"
            >
              <span className="text-sm">⏭</span>
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-0.5 bg-glass/30 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-[#1DB954]"
            initial={{ width: `${progress}%` }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1, ease: "linear" }}
          />
        </div>
      </div>
    );
  }

  // Palette row variant (for showing in CommandPalette)
  if (variant === "palette-row") {
    return (
      <div className="w-full p-3 border-b border-glass/50 bg-glass/30">
        <div className="flex items-center gap-3">
          {/* Album art */}
          <img
            src={albumSmallImage}
            alt={track.album.name}
            loading="lazy"
            className="w-10 h-10 rounded object-cover"
          />

          {/* Track info */}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{track.name}</div>
            <div className="text-xs text-muted truncate">
              {track.artists.map(a => a.name).join(", ")}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={handlePrevious}
              className="p-1.5 rounded hover:bg-glass-hover transition-colors"
              title="Previous"
            >
              <span className="text-sm">⏮</span>
            </button>
            <button
              onClick={handlePlayPause}
              className="p-1.5 rounded hover:bg-glass-hover transition-colors"
              title={playbackStatus.is_playing ? "Pause" : "Play"}
            >
              <span className="text-sm">{playbackStatus.is_playing ? "⏸" : "▶️"}</span>
            </button>
            <button
              onClick={handleNext}
              className="p-1.5 rounded hover:bg-glass-hover transition-colors"
              title="Next"
            >
              <span className="text-sm">⏭</span>
            </button>
          </div>

          {/* Device indicator */}
          {playbackStatus.device && (
            <div className="text-xs text-[#1DB954]">
              {playbackStatus.device.name}
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1 bg-glass rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-[#1DB954]"
            initial={{ width: `${progress}%` }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1 }}
          />
        </div>
      </div>
    );
  }

  // Launcher variant (compact bar at bottom)
  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 20, opacity: 0 }}
        className="w-full px-4 py-3 border-t border-glass/30 bg-glass/20 backdrop-blur-xl"
      >
        <div className="flex items-center gap-3">
          {/* Album art */}
          <img
            src={albumSmallImage}
            alt={track.album.name}
            loading="lazy"
            className="w-12 h-12 rounded shadow-lg object-cover"
          />

          {/* Track info */}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{track.name}</div>
            <div className="text-xs text-muted truncate">
              {track.artists.map(a => a.name).join(", ")}
            </div>
            {playbackStatus.device && (
              <div className="text-xs text-[#1DB954] mt-0.5">
                ▸ {playbackStatus.device.name}
              </div>
            )}
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevious}
              className="p-2 rounded-lg hover:bg-glass-hover active:scale-95 transition-all"
              title="Previous (Cmd+Left)"
            >
              <span className="text-base">⏮</span>
            </button>
            <button
              onClick={handlePlayPause}
              className="p-2 rounded-lg hover:bg-glass-hover active:scale-95 transition-all bg-[#1DB954]/10"
              title={playbackStatus.is_playing ? "Pause (Space)" : "Play (Space)"}
            >
              <span className="text-lg">{playbackStatus.is_playing ? "⏸" : "▶️"}</span>
            </button>
            <button
              onClick={handleNext}
              className="p-2 rounded-lg hover:bg-glass-hover active:scale-95 transition-all"
              title="Next (Cmd+Right)"
            >
              <span className="text-base">⏭</span>
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1 bg-glass rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-[#1DB954]"
            initial={{ width: `${progress}%` }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1, ease: "linear" }}
          />
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
