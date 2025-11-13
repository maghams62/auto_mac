"""
Rate limiter for OpenAI API calls using token bucket algorithm.

Respects OpenAI's RPM (requests per minute) and TPM (tokens per minute) limits
while maximizing throughput.
"""

import asyncio
import time
import logging
from collections import deque
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    rpm_limit: int = 10000      # Requests per minute
    tpm_limit: int = 2_000_000  # Tokens per minute
    burst_size: int = 100       # Allow bursts up to this many requests
    safety_margin: float = 0.9  # Use 90% of limits to be safe


class OpenAIRateLimiter:
    """
    Token bucket rate limiter for OpenAI API calls.
    
    Tracks both RPM (requests per minute) and TPM (tokens per minute)
    to stay within OpenAI's rate limits while maximizing throughput.
    
    Usage:
        limiter = OpenAIRateLimiter(rpm_limit=10000, tpm_limit=2000000)
        
        # Before making API call
        await limiter.acquire(estimated_tokens=1000)
        
        # Make API call
        response = await openai_call()
        
        # Record actual usage
        limiter.record_usage(actual_tokens=response.usage.total_tokens)
    """
    
    def __init__(
        self,
        rpm_limit: int = 10000,
        tpm_limit: int = 2_000_000,
        burst_size: int = 100,
        safety_margin: float = 0.9
    ):
        """
        Initialize rate limiter.
        
        Args:
            rpm_limit: Requests per minute limit
            tpm_limit: Tokens per minute limit
            burst_size: Allow bursts up to this size
            safety_margin: Use this fraction of limits (0.9 = 90%)
        """
        self.config = RateLimitConfig(
            rpm_limit=int(rpm_limit * safety_margin),
            tpm_limit=int(tpm_limit * safety_margin),
            burst_size=burst_size,
            safety_margin=safety_margin
        )
        
        # Sliding window tracking (last 60 seconds)
        self.request_times = deque()
        self.token_usage = deque()
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
        
        # Statistics
        self.total_requests = 0
        self.total_tokens = 0
        self.total_wait_time = 0.0
        self.rate_limit_hits = 0
        
        logger.info(
            f"[RATE LIMITER] Initialized with RPM={self.config.rpm_limit}, "
            f"TPM={self.config.tpm_limit}, safety_margin={safety_margin}"
        )
    
    async def acquire(self, estimated_tokens: int = 1000) -> float:
        """
        Acquire rate limit slot before making API call.
        
        Will wait if necessary to stay within rate limits.
        
        Args:
            estimated_tokens: Estimated token usage for this request
            
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        async with self.lock:
            now = time.time()
            wait_time = 0.0
            
            # Clean up old entries (>60 seconds old)
            self._cleanup_old_entries(now)
            
            # Check RPM limit
            rpm_wait = self._check_rpm_limit(now)
            
            # Check TPM limit
            tpm_wait = self._check_tpm_limit(now, estimated_tokens)
            
            # Wait for the longer of the two
            wait_time = max(rpm_wait, tpm_wait)
            
            if wait_time > 0:
                self.rate_limit_hits += 1
                logger.debug(
                    f"[RATE LIMITER] Waiting {wait_time:.2f}s "
                    f"(RPM: {len(self.request_times)}/{self.config.rpm_limit}, "
                    f"TPM: {sum(self.token_usage)}/{self.config.tpm_limit})"
                )
                await asyncio.sleep(wait_time)
                self.total_wait_time += wait_time
                
                # Clean up again after waiting
                now = time.time()
                self._cleanup_old_entries(now)
            
            # Record this request
            self.request_times.append(now)
            self.token_usage.append(estimated_tokens)
            self.total_requests += 1
            self.total_tokens += estimated_tokens
            
            return wait_time
    
    def record_usage(self, actual_tokens: int):
        """
        Record actual token usage after API call completes.
        
        This corrects the estimated tokens with actual usage.
        
        Args:
            actual_tokens: Actual tokens used by the API call
        """
        if self.token_usage:
            # Update the last entry with actual usage
            estimated = self.token_usage[-1]
            self.token_usage[-1] = actual_tokens
            
            # Update total
            self.total_tokens = self.total_tokens - estimated + actual_tokens
    
    def _cleanup_old_entries(self, now: float):
        """Remove entries older than 60 seconds."""
        cutoff = now - 60.0
        
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
            self.token_usage.popleft()
    
    def _check_rpm_limit(self, now: float) -> float:
        """
        Check if RPM limit would be exceeded.
        
        Returns:
            Wait time needed in seconds (0 if no wait needed)
        """
        if len(self.request_times) < self.config.rpm_limit:
            return 0.0
        
        # Calculate when oldest request will age out
        oldest = self.request_times[0]
        wait_time = 60.0 - (now - oldest)
        
        return max(0.0, wait_time)
    
    def _check_tpm_limit(self, now: float, estimated_tokens: int) -> float:
        """
        Check if TPM limit would be exceeded.
        
        Returns:
            Wait time needed in seconds (0 if no wait needed)
        """
        current_tokens = sum(self.token_usage)
        
        if current_tokens + estimated_tokens <= self.config.tpm_limit:
            return 0.0
        
        # Calculate when enough tokens will age out
        if not self.request_times:
            return 0.0
        
        oldest = self.request_times[0]
        wait_time = 60.0 - (now - oldest)
        
        return max(0.0, wait_time)
    
    def get_stats(self) -> dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with usage statistics
        """
        now = time.time()
        self._cleanup_old_entries(now)
        
        current_rpm = len(self.request_times)
        current_tpm = sum(self.token_usage)
        
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_wait_time": self.total_wait_time,
            "rate_limit_hits": self.rate_limit_hits,
            "current_rpm": current_rpm,
            "current_tpm": current_tpm,
            "rpm_utilization": current_rpm / self.config.rpm_limit if self.config.rpm_limit > 0 else 0,
            "tpm_utilization": current_tpm / self.config.tpm_limit if self.config.tpm_limit > 0 else 0,
            "avg_wait_time": self.total_wait_time / self.total_requests if self.total_requests > 0 else 0,
        }
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.total_requests = 0
        self.total_tokens = 0
        self.total_wait_time = 0.0
        self.rate_limit_hits = 0


# Global rate limiter instance
_global_rate_limiter: Optional[OpenAIRateLimiter] = None


def get_rate_limiter(
    rpm_limit: int = 10000,
    tpm_limit: int = 2_000_000
) -> OpenAIRateLimiter:
    """
    Get or create global rate limiter instance.
    
    Args:
        rpm_limit: Requests per minute limit
        tpm_limit: Tokens per minute limit
        
    Returns:
        Global rate limiter instance
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = OpenAIRateLimiter(
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit
        )
    
    return _global_rate_limiter

