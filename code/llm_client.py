import os
import json
import urllib.request
import urllib.error
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def call_gemini(prompt, system, is_json, api_key, model="gemini-3.5-flash-lite", media_data=None, mime_type=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    parts = [{"text": prompt}]
    
    if media_data and mime_type:
        import base64
        parts.insert(0, {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(media_data).decode("utf-8")
            }
        })
        
    payload = {"contents": [{"role": "user", "parts": parts}]}
    if system: payload["systemInstruction"] = {"parts": [{"text": system}]}
    if is_json: payload["generationConfig"] = {"responseMimeType": "application/json"}
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return {"text": text, "usage": usage}

def call_claude(prompt, system, is_json, api_key):
    url = "https://api.anthropic.com/v1/messages"
    if is_json: prompt += "\n\nPlease output valid JSON only."
    payload = {"model": "claude-3-haiku-20240307", "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
    if system: payload["system"] = system
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    req = urllib.request.Request(url, json.dumps(payload).encode(), headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
        text = data["content"][0]["text"]
        usage = data.get("usage", {})
        return {"text": text, "usage": usage}

def call_openrouter(prompt, system, is_json, api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    payload = {"model": "meta-llama/llama-3-8b-instruct:free", "messages": messages}
    if is_json: payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, json.dumps(payload).encode(), headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {"text": text, "usage": usage}

def call_model(prompt, system=None, response_format=None, media_data=None, mime_type=None):
    providers = ["gemini", "claude", "openrouter"]
    adapters = {"gemini": call_gemini, "claude": call_claude, "openrouter": call_openrouter}
    keys = {"gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
    
    history = []
    for attempt, provider in enumerate(providers, 1):
        api_key = os.getenv(keys[provider])
        if not api_key:
            history.append(f"{provider}: skipped (missing {keys[provider]})")
            continue
            
        if media_data and provider != "gemini":
            history.append(f"{provider}: skipped (media input not supported yet)")
            continue
            
        try:
            logging.info(f"Attempting {provider}...")
            if provider == "gemini":
                result = adapters[provider](prompt, system, response_format == "json", api_key, media_data=media_data, mime_type=mime_type)
            else:
                result = adapters[provider](prompt, system, response_format == "json", api_key)
            return {
                "text": result["text"], 
                "provider_used": provider, 
                "attempt_count": attempt,
                "usage": result.get("usage", {})
            }
        except urllib.error.HTTPError as e:
            err_msg = f"HTTP {e.code}: {e.read().decode()}"
            history.append(f"{provider}: {err_msg}")
            if e.code in (429, 503, 529):
                logging.warning(f"[{provider}] Rate-limit/Quota error -> {err_msg}")
            else:
                logging.warning(f"[{provider}] API error -> {err_msg}")
        except Exception as e:
            history.append(f"{provider}: {str(e)}")
            logging.warning(f"[{provider}] Internal error -> {str(e)}")
            
    raise RuntimeError(f"All providers failed.\nHistory:\n" + "\n".join(history))

if __name__ == "__main__":
    print("Testing call_model...")
    print("Will attempt Gemini -> Claude -> OpenRouter.\n")
    try:
        response = call_model("What is 2+2? Answer in one word.", system="You are a math bot.")
        print(f"\nSUCCESS!\n{json.dumps(response, indent=2)}")
    except Exception as e:
        print(f"\nFAILED:\n{e}")
