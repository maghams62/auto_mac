"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { getApiBaseUrl } from "@/lib/apiConfig";

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
  };
  progress_ms: number;
}

/**
 * Compact Spotify Mini Player
 * Design inspired by macOS style - clean, minimal, no actions
 */
export default function SpotifyMiniPlayerCompact() {
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const apiBaseUrl = getApiBaseUrl();

  // Fetch Spotify status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/spotify/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        setIsAuthenticated(true);
      } else if (response.status === 401) {
        setIsAuthenticated(false);
        setStatus(null);
      }
    } catch (error) {
      console.error("Failed to fetch Spotify status:", error);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  // Poll for status updates
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, status?.is_playing ? 1000 : 3000);
    return () => clearInterval(interval);
  }, [fetchStatus, status?.is_playing]);

  // Playback controls
  const handlePlayPause = useCallback(async () => {
    try {
      const endpoint = status?.is_playing ? 'pause' : 'play';
      await fetch(`${apiBaseUrl}/api/spotify/${endpoint}`, { method: 'POST' });
      await fetchStatus();
    } catch (error) {
      console.error("Play/pause failed:", error);
    }
  }, [apiBaseUrl, status?.is_playing, fetchStatus]);

  const handleNext = useCallback(async () => {
    try {
      await fetch(`${apiBaseUrl}/api/spotify/next`, { method: 'POST' });
      setTimeout(fetchStatus, 500);
    } catch (error) {
      console.error("Next track failed:", error);
    }
  }, [apiBaseUrl, fetchStatus]);

  const handlePrevious = useCallback(async () => {
    try {
      await fetch(`${apiBaseUrl}/api/spotify/previous`, { method: 'POST' });
      setTimeout(fetchStatus, 500);
    } catch (error) {
      console.error("Previous track failed:", error);
    }
  }, [apiBaseUrl, fetchStatus]);

  // Don't render if loading or not authenticated
  if (isLoading || !isAuthenticated || !status?.item) {
    return null;
  }

  const track = status.item;
  const albumArt = track.album.images[0]?.url || track.album.images[1]?.url;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="fixed top-20 right-6 z-50"
    >
      {/* Main Player Card */}
      <div className="bg-black/90 backdrop-blur-xl rounded-2xl shadow-2xl overflow-hidden w-[320px]">
        {/* Close Button */}
        <div className="absolute top-3 right-3 z-10">
          <button
            className="w-6 h-6 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
            aria-label="Close"
          >
            <svg className="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Album Art */}
        {albumArt && (
          <div className="relative w-full aspect-square">
            <img
              src={albumArt}
              alt={track.album.name}
              className="w-full h-full object-cover"
            />
            {/* Gradient Overlay */}
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/60" />
          </div>
        )}

        {/* Track Info & Controls */}
        <div className="p-4">
          {/* Track Name */}
          <h3 className="text-white font-semibold text-base truncate mb-1">
            {track.name}
          </h3>

          {/* Artist */}
          <p className="text-white/60 text-sm truncate mb-4">
            {track.artists.map(a => a.name).join(", ")}
          </p>

          {/* Playback Controls */}
          <div className="flex items-center justify-center gap-6">
            {/* Shuffle (disabled) */}
            <button
              className="text-white/40 hover:text-white/60 transition-colors disabled:cursor-not-allowed"
              disabled
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z"/>
              </svg>
            </button>

            {/* Previous */}
            <button
              onClick={handlePrevious}
              className="text-white/70 hover:text-white transition-colors"
            >
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
              </svg>
            </button>

            {/* Play/Pause */}
            <button
              onClick={handlePlayPause}
              className="bg-white text-black rounded-full w-12 h-12 flex items-center justify-center hover:scale-105 transition-transform shadow-lg"
            >
              {status.is_playing ? (
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
              ) : (
                <svg className="w-6 h-6 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              )}
            </button>

            {/* Next */}
            <button
              onClick={handleNext}
              className="text-white/70 hover:text-white transition-colors"
            >
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
              </svg>
            </button>

            {/* Queue (disabled) */}
            <button
              className="text-white/40 hover:text-white/60 transition-colors disabled:cursor-not-allowed"
              disabled
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/>
              </svg>
            </button>

            {/* Volume (disabled) */}
            <button
              className="text-white/40 hover:text-white/60 transition-colors disabled:cursor-not-allowed"
              disabled
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
