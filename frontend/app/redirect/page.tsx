"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/apiConfig";

export default function RedirectPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const [status, setStatus] = useState<"processing" | "success" | "error">("processing");
  const [message, setMessage] = useState("Processing redirect...");

  useEffect(() => {
    const handleRedirect = async () => {
      try {
        // Get redirect parameters
        const redirectTo = searchParams.get("to");
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const error = searchParams.get("error");
        const errorDescription = searchParams.get("error_description");

        // Handle OAuth errors
        if (error) {
          setStatus("error");
          setMessage(
            errorDescription || error || "Authentication failed. Please try again."
          );
          // Redirect to home after 3 seconds
          setTimeout(() => {
            router.push("/");
          }, 3000);
          return;
        }

        // Handle OAuth callback with code
        if (code) {
          // Send code to backend for processing
          try {
            const response = await fetch(`${apiBaseUrl}/api/auth/callback`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                code,
                state,
                redirect_uri: window.location.origin + "/redirect",
              }),
            });

            if (!response.ok) {
              const errorData = await response.json().catch(() => ({}));
              throw new Error(errorData.detail || "Failed to process authentication");
            }

            const data = await response.json();
            setStatus("success");
            setMessage(data.message || "Authentication successful!");

            // Redirect to specified destination or home
            const destination = data.redirect_to || redirectTo || "/";
            setTimeout(() => {
              router.push(destination);
            }, 2000);
          } catch (err) {
            setStatus("error");
            setMessage(
              err instanceof Error ? err.message : "Failed to complete authentication. Please try again."
            );
            setTimeout(() => {
              router.push("/");
            }, 3000);
          }
          return;
        }

        // Handle simple redirect
        if (redirectTo) {
          // Validate redirect URL (prevent open redirects)
          try {
            const url = new URL(redirectTo, window.location.origin);
            // Only allow redirects to same origin or configured allowed domains
            if (
              url.origin === window.location.origin ||
              redirectTo.startsWith("/")
            ) {
              router.push(redirectTo);
              return;
            }
          } catch {
            // Invalid URL, fall through to error
          }
        }

        // No valid redirect found, go to home
        setStatus("error");
        setMessage("Invalid redirect parameters.");
        setTimeout(() => {
          router.push("/");
        }, 2000);
      } catch (err) {
        setStatus("error");
        setMessage("An error occurred during redirect.");
        setTimeout(() => {
          router.push("/");
        }, 2000);
      }
    };

    handleRedirect();
  }, [searchParams, router, apiBaseUrl]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="text-center">
        {status === "processing" && (
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        )}
        {status === "success" && (
          <div className="text-green-500 text-4xl mb-4">✓</div>
        )}
        {status === "error" && (
          <div className="text-red-500 text-4xl mb-4">✗</div>
        )}
        <p className="text-white text-lg">{message}</p>
      </div>
    </div>
  );
}

