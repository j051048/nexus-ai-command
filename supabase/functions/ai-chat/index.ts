import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const BACKEND_URL =
  Deno.env.get("BACKEND_URL") || "https://aizhz.zeabur.app";

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const authorization = req.headers.get("Authorization");
    if (!authorization) {
      return new Response(
        JSON.stringify({ error: "Missing Authorization header" }),
        {
          status: 401,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const body = await req.text();

    // Proxy the request to the backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: {
        Authorization: authorization,
        "Content-Type": "application/json",
      },
      body,
    });

    if (!backendResponse.ok) {
      // Forward error responses as-is
      const errorText = await backendResponse.text();
      return new Response(errorText, {
        status: backendResponse.status,
        headers: {
          ...corsHeaders,
          "Content-Type":
            backendResponse.headers.get("Content-Type") || "application/json",
        },
      });
    }

    // Stream the SSE response back to the client
    return new Response(backendResponse.body, {
      headers: {
        ...corsHeaders,
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (e) {
    console.error("AI chat proxy error:", e);
    return new Response(
      JSON.stringify({
        error: "代理服务暂不可用，正在切换到增强直连模式...",
        fallback: true,
      }),
      {
        status: 502,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
