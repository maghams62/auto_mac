"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface SpotifyPlayerProps {
  onDeviceReady?: (deviceId: string) => void;
}

interface PlaybackState {
  paused: boolean;
  position: number;
  duration: number;
  track_window: {
    current_track: {
      name: string;
      artists: Array<{ name: string }>;
      album: {
        name: string;
        images: Array<{ url: string }>;
      };
      uri: string;
    };
  };
}

declare global {
  interface Window {
    onSpotifyWebPlaybackSDKReady: () => void;
    Spotify: {
      Player: new (config: {
        name: string;
        getOAuthToken: (cb: (token: string) => void) => void;
        volume: number;
      }) => SpotifyPlayerInstance;
    };
  }
}

interface SpotifyPlayerInstance {
  connect(): Promise<boolean>;
  disconnect(): void;
  addListener(event: string, callback: (data: any) => void): void;
  removeListener(event: string, callback?: (data: any) => void): void;
  getCurrentState(): Promise<PlaybackState | null>;
  setVolume(volume: number): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  togglePlay(): Promise<void>;
  nextTrack(): Promise<void>;
  previousTrack(): Promise<void>;
  seek(position: number): Promise<void>;
}

export default function SpotifyPlayer({ onDeviceReady }: SpotifyPlayerProps) {
  const [player, setPlayer] = useState<SpotifyPlayerInstance | null>(null);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [currentTrack, setCurrentTrack] = useState<PlaybackState["track_window"]["current_track"] | null>(null);
  const [isPaused, setIsPaused] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [authStatus, setAuthStatus] = useState<"checking" | "authenticated" | "unauthenticated">("checking");
  const [isHovered, setIsHovered] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showConnecting, setShowConnecting] = useState(false);
  const [scrollToBottomVisible, setScrollToBottomVisible] = useState(false);

  const apiBaseUrl = getApiBaseUrl();
  const scriptLoadedRef = useRef(false);
  const playerInitializedRef = useRef(false);

  // Detect ScrollToBottom button visibility for collision avoidance
  useEffect(() => {
    const checkScrollToBottomVisibility = () => {
      const scrollToBottomButton = document.querySelector('[aria-label="Scroll to bottom"]');
      if (scrollToBottomButton) {
        const computedStyle = window.getComputedStyle(scrollToBottomButton);
        const isVisible = computedStyle.display !== 'none' && computedStyle.opacity !== '0';
        setScrollToBottomVisible(isVisible);
      } else {
        setScrollToBottomVisible(false);
      }
    };

    // Check immediately
    checkScrollToBottomVisibility();

    // Set up observer for DOM changes
    const observer = new MutationObserver(checkScrollToBottomVisibility);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['style', 'class']
    });

    // Also check periodically in case of dynamic visibility changes
    const interval = setInterval(checkScrollToBottomVisibility, 1000);

    return () => {
      observer.disconnect();
      clearInterval(interval);
    };
  }, []);

  // Check authentication status
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/spotify/auth-status`);
        const data = await response.json();
        console.log("Spotify auth status:", data);
        setIsAuthenticated(data.authenticated || false);
        setAuthStatus(data.authenticated ? "authenticated" : "unauthenticated");
      } catch (error) {
        console.error("Failed to check Spotify auth status:", error);
        setAuthStatus("unauthenticated");
      }
    };

    // Check immediately
    checkAuth();
    
    // Check frequently for the first 30 seconds (in case user just authenticated)
    const quickCheckInterval = setInterval(checkAuth, 2000);
    setTimeout(() => {
      clearInterval(quickCheckInterval);
    }, 30000);
    
    // Then check every 5 minutes
    const slowCheckInterval = setInterval(checkAuth, 5 * 60 * 1000);
    
    // Also check when window regains focus (user might have authenticated in another tab)
    const handleFocus = () => {
      console.log("Window focused, re-checking Spotify auth status");
      checkAuth();
    };
    window.addEventListener('focus', handleFocus);
    
    return () => {
      clearInterval(quickCheckInterval);
      clearInterval(slowCheckInterval);
      window.removeEventListener('focus', handleFocus);
    };
  }, [apiBaseUrl]);

  // Get access token from backend
  const getAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/spotify/token`);
      const data = await response.json();
      return data.access_token || null;
    } catch (error) {
      console.error("Failed to get Spotify access token:", error);
      return null;
    }
  }, [apiBaseUrl]);

  // Load Spotify Web Playback SDK
  useEffect(() => {
    if (scriptLoadedRef.current || !isAuthenticated) return;

    const script = document.createElement("script");
    script.src = "https://sdk.scdn.co/spotify-player.js";
    script.async = true;
    document.body.appendChild(script);
    scriptLoadedRef.current = true;

    return () => {
      if (script.parentNode) {
        script.parentNode.removeChild(script);
      }
    };
  }, [isAuthenticated]);

  // Initialize Spotify Player
  useEffect(() => {
    if (!isAuthenticated || playerInitializedRef.current) return;
    setShowConnecting(true);

    window.onSpotifyWebPlaybackSDKReady = () => {
      if (playerInitializedRef.current) return;
      playerInitializedRef.current = true;

      const spotifyPlayer = new window.Spotify.Player({
        name: "Cerebro OS Web Player",
        getOAuthToken: async (cb) => {
          const token = await getAccessToken();
          if (token) {
            cb(token);
          }
        },
        volume: 0.7,
      });

      // Ready
      spotifyPlayer.addListener("ready", ({ device_id }: { device_id: string }) => {
        console.log("Spotify Player Ready with Device ID:", device_id);
        setDeviceId(device_id);
        setIsActive(true);
        setShowConnecting(false);

        if (onDeviceReady) {
          onDeviceReady(device_id);
        }

        fetch(`${apiBaseUrl}/api/spotify/register-device`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device_id }),
        }).catch(err => console.error("Failed to register device:", err));
      });

      spotifyPlayer.addListener("not_ready", ({ device_id }: { device_id: string }) => {
        console.log("Spotify Player Not Ready:", device_id);
        setIsActive(false);
      });

      spotifyPlayer.addListener("player_state_changed", (state: PlaybackState | null) => {
        if (!state) {
          setCurrentTrack(null);
          setIsPaused(true);
          setPosition(0);
          setDuration(0);
          return;
        }

        setCurrentTrack(state.track_window.current_track);
        setIsPaused(state.paused);
        setPosition(state.position);
        setDuration(state.duration);
      });

      spotifyPlayer.addListener("initialization_error", ({ message }: { message: string }) => {
        console.error("Spotify initialization error:", message);
        setShowConnecting(false);
      });

      spotifyPlayer.addListener("authentication_error", ({ message }: { message: string }) => {
        console.error("Spotify authentication error:", message);
        setIsAuthenticated(false);
        setAuthStatus("unauthenticated");
        setShowConnecting(false);
      });

      spotifyPlayer.addListener("account_error", ({ message }: { message: string }) => {
        console.error("Spotify account error:", message);
        setShowConnecting(false);
      });

      spotifyPlayer.addListener("playback_error", ({ message }: { message: string }) => {
        console.error("Spotify playback error:", message);
      });

      spotifyPlayer.connect();
      setPlayer(spotifyPlayer);
    };

    return () => {
      if (player) {
        player.disconnect();
      }
    };
  }, [isAuthenticated, getAccessToken, onDeviceReady, apiBaseUrl]);

  const handleLogin = () => {
    window.location.href = `${apiBaseUrl}/api/spotify/login`;
  };

  const togglePlayPause = async () => {
    if (!player) return;
    try {
      await player.togglePlay();
    } catch (error) {
      console.error("Failed to toggle play/pause:", error);
    }
  };

  const skipToNext = async () => {
    if (!player) return;
    try {
      await player.nextTrack();
    } catch (error) {
      console.error("Failed to skip to next track:", error);
    }
  };

  const skipToPrevious = async () => {
    if (!player) return;
    try {
      await player.previousTrack();
    } catch (error) {
      console.error("Failed to skip to previous track:", error);
    }
  };

  const formatTime = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Don't show anything if checking auth
  if (authStatus === "checking") {
    return null;
  }

  // Show login button if not authenticated
  if (!isAuthenticated) {
    return (
      <div className={`fixed ${scrollToBottomVisible ? 'bottom-20' : 'bottom-6'} right-6 z-50 animate-in fade-in slide-in-from-bottom-4 duration-500 transition-all`}>
        <div className="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-gray-700/50 rounded-2xl p-5 shadow-2xl hover:shadow-green-500/20 transition-all duration-300 hover:scale-105">
          <div className="flex items-center gap-4">
            <div className="flex-shrink-0">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-full flex items-center justify-center shadow-lg shadow-green-500/30">
                <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                </svg>
              </div>
            </div>
            <div className="flex-1">
              <div className="text-white font-semibold text-base mb-1">Connect Spotify</div>
              <div className="text-gray-400 text-xs">Premium account required</div>
            </div>
            <button
              onClick={handleLogin}
              className="bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white px-6 py-2.5 rounded-full text-sm font-semibold transition-all duration-300 hover:scale-105 active:scale-95 shadow-lg shadow-green-500/30 hover:shadow-green-500/50"
            >
              Connect
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Minimized view
  if (isMinimized) {
    return (
      <div className={`fixed ${scrollToBottomVisible ? 'bottom-20' : 'bottom-6'} right-6 z-50 animate-in fade-in slide-in-from-bottom-4 duration-300 transition-all`}>
        <button
          onClick={() => setIsMinimized(false)}
          className="group bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-2xl hover:shadow-green-500/20 transition-all duration-300 hover:scale-105 active:scale-95"
        >
          <div className="flex items-center gap-3 p-4">
            <div className="relative">
              <div className={`w-2.5 h-2.5 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-500'}`} />
              {isActive && <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-green-500 animate-ping" />}
            </div>
            {currentTrack ? (
              <div className="flex items-center gap-3">
                {currentTrack.album.images[0] && (
                  <img
                    src={currentTrack.album.images[0].url}
                    alt={currentTrack.album.name}
                    className="w-8 h-8 rounded-lg shadow-lg"
                  />
                )}
                <div className="text-left">
                  <div className="text-white text-sm font-medium max-w-[160px] truncate">
                    {currentTrack.name}
                  </div>
                  <div className="text-gray-400 text-xs max-w-[160px] truncate">
                    {currentTrack.artists.map(a => a.name).join(", ")}
                  </div>
                </div>
              </div>
            ) : (
              <span className="text-white text-sm font-medium">Spotify Player</span>
            )}
            <svg className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </div>
        </button>
      </div>
    );
  }

  // Full player view
  return (
    <div
      className={`fixed ${scrollToBottomVisible ? 'bottom-20' : 'bottom-6'} right-6 z-50 animate-in fade-in slide-in-from-bottom-4 duration-500 transition-all`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-2xl hover:shadow-green-500/20 transition-all duration-300 w-96 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700/50">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className={`w-2.5 h-2.5 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-500'} transition-colors duration-300`} />
              {isActive && <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-green-500 animate-ping" />}
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
              </svg>
              <span className="text-white text-sm font-semibold">Spotify</span>
            </div>
          </div>
          <button
            onClick={() => setIsMinimized(true)}
            className="text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-lg p-1.5 transition-all duration-200 active:scale-95"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Now Playing or Loading */}
        {showConnecting ? (
          <div className="p-8 text-center">
            <div className="relative w-16 h-16 mx-auto mb-4">
              <div className="absolute inset-0 border-4 border-gray-700/30 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-t-green-500 rounded-full animate-spin"></div>
            </div>
            <div className="text-white font-medium mb-1">Connecting to Spotify...</div>
            <div className="text-gray-400 text-sm">Setting up your player</div>
          </div>
        ) : currentTrack ? (
          <div className="p-5">
            {/* Album Art & Track Info */}
            <div className="relative mb-5 group">
              <div className="relative overflow-hidden rounded-xl shadow-2xl">
                {currentTrack.album.images[0] && (
                  <>
                    <img
                      src={currentTrack.album.images[0].url}
                      alt={currentTrack.album.name}
                      className="w-full aspect-square object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  </>
                )}
              </div>
              <div className="mt-4">
                <div className="text-white font-semibold text-lg mb-1 truncate group-hover:text-green-400 transition-colors duration-200">
                  {currentTrack.name}
                </div>
                <div className="text-gray-400 text-sm truncate">
                  {currentTrack.artists.map(a => a.name).join(", ")}
                </div>
                <div className="text-gray-500 text-xs truncate mt-1">
                  {currentTrack.album.name}
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            {duration > 0 && (
              <div className="mb-4">
                <div className="h-1.5 bg-gray-700/50 rounded-full overflow-hidden backdrop-blur-sm">
                  <div
                    className="h-full bg-gradient-to-r from-green-500 to-green-400 transition-all duration-300 rounded-full"
                    style={{ width: `${(position / duration) * 100}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-500 mt-1.5">
                  <span>{formatTime(position)}</span>
                  <span>{formatTime(duration)}</span>
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="flex items-center justify-center gap-6">
              <button
                onClick={skipToPrevious}
                className="text-gray-400 hover:text-white hover:scale-110 transition-all duration-200 active:scale-95"
                title="Previous track"
              >
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
                </svg>
              </button>
              <button
                onClick={togglePlayPause}
                className="bg-gradient-to-br from-white to-gray-100 hover:from-gray-100 hover:to-gray-200 text-black rounded-full p-3.5 transition-all duration-200 hover:scale-110 active:scale-95 shadow-lg hover:shadow-xl"
                title={isPaused ? "Play" : "Pause"}
              >
                {isPaused ? (
                  <svg className="w-6 h-6 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 4h4v16H6zm8 0h4v16h-4z" />
                  </svg>
                )}
              </button>
              <button
                onClick={skipToNext}
                className="text-gray-400 hover:text-white hover:scale-110 transition-all duration-200 active:scale-95"
                title="Next track"
              >
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
                </svg>
              </button>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center">
            <div className="w-16 h-16 bg-gradient-to-br from-green-500/20 to-green-600/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/30">
              <svg className="w-8 h-8 text-green-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
              </svg>
            </div>
            <div className="text-white font-medium mb-1">
              {isActive ? "Ready to play music" : "Connecting..."}
            </div>
            <div className="text-gray-400 text-sm">
              {isActive ? "Start playing from Cerebro OS" : "Initializing player..."}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
