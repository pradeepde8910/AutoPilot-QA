from typing import Dict, Any, Optional, List, Union
import json
import time
import base64
import requests
from groq import Groq
from config.settings import settings
from utils.logger import log
from core.exceptions import LLMReasoningError

# Maximum number of retries on rate limit hit
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 5

def _is_rate_limit_error(e: Exception) -> bool:
    """Checks if an exception is a Groq rate limit (429) error."""
    return "429" in str(e) or "rate_limit_exceeded" in str(e)

def _with_retry(fn, switch_key_fn=None, max_retries=MAX_RETRIES):
    """Executes fn with exponential backoff retry on rate limit errors.
    On first rate limit, attempts to switch to fallback key before retrying.
    """
    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < max_retries:
                # Try switching to fallback key first
                if switch_key_fn and switch_key_fn():
                    log.info("Retrying immediately with fallback key...")
                    return fn() # Retry immediately after switch
                wait_time = backoff * (2 ** attempt)
                log.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                raise

from google import genai
from google.genai import types

class GeminiClient:
    """Official SDK client for Gemini."""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        
    def _call(self, model: str, messages: list, temperature: float = 0.7, json_mode: bool = False):
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    # Handle vision
                    parts = []
                    for c in content:
                        if c.get("type") == "text":
                            parts.append(types.Part.from_text(text=c["text"]))
                        elif c.get("type") == "image_url":
                            url = c["image_url"]["url"]
                            if url.startswith("data:image/jpeg;base64,"):
                                b64_data = url.split(",")[1]
                                parts.append(types.Part.from_bytes(data=base64.b64decode(b64_data), mime_type="image/jpeg"))
                    contents.append(types.Content(role="user", parts=parts))
                else:
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
            elif msg["role"] == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg["content"])]))
                
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction
        )
        if json_mode:
            config.response_mime_type = "application/json"
            
        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )
        return response.text

class LLMClient:
    def __init__(self):
        self._primary_key = None
        self._gemini_key = None
        self._groq_client = None
        self._gemini_client = None
        self._using_gemini_fallback = False
        
        self.default_model = settings.DEFAULT_LLM_MODEL
        self.vision_model = "llama-3.2-11b-vision-preview"
        
        self.gemini_default_model = settings.GEMINI_DEFAULT_MODEL
        self.gemini_vision_model = settings.GEMINI_VISION_MODEL

    @property
    def groq_client(self):
        if self._groq_client is None or self._primary_key != settings.GROQ_API_KEY:
            self._primary_key = settings.GROQ_API_KEY
            self._groq_client = Groq(api_key=self._primary_key) if self._primary_key else None
        return self._groq_client

    @property
    def gemini_client(self):
        if self._gemini_client is None or self._gemini_key != settings.GEMINI_API_KEY:
            self._gemini_key = settings.GEMINI_API_KEY
            self._gemini_client = GeminiClient(api_key=self._gemini_key) if self._gemini_key else None
        return self._gemini_client

    def reset_fallback(self) -> None:
        self._using_gemini_fallback = False

    def _switch_to_fallback(self) -> bool:
        """Switches to Gemini fallback. Returns True if switched."""
        if self.gemini_client and not self._using_gemini_fallback:
            log.warning("Primary Groq key rate limited. Switching to GEMINI FALLBACK automatically!")
            self._using_gemini_fallback = True
            return True
        return False

    def chat(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> str:
        log.info("LLMClient.chat called")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        def _call():
            if self._using_gemini_fallback:
                return self.gemini_client._call(model=self.gemini_default_model, messages=messages, temperature=0.7)
            else:
                response = self.groq_client.chat.completions.create(
                    model=model or self.default_model,
                    messages=messages,
                    temperature=0.7,
                )
                return response.choices[0].message.content

        try:
            return _with_retry(_call, switch_key_fn=self._switch_to_fallback)
        except Exception as e:
            log.error(f"Chat completion failed: {e}")
            raise LLMReasoningError(f"Chat failed: {e}")

    def reason(self, prompt: str, context: str, model: Optional[str] = None) -> str:
        log.info("LLMClient.reason called")
        messages = [
            {"role": "system", "content": "You are an analytical reasoning agent. Carefully analyze the provided context to answer the user's prompt."},
            {"role": "user", "content": f"Context:\n{context}\n\nTask:\n{prompt}"}
        ]

        def _call():
            if self._using_gemini_fallback:
                return self.gemini_client._call(model=self.gemini_default_model, messages=messages, temperature=0.2)
            else:
                response = self.groq_client.chat.completions.create(
                    model=model or self.default_model,
                    messages=messages,
                    temperature=0.2,
                )
                return response.choices[0].message.content

        try:
            return _with_retry(_call, switch_key_fn=self._switch_to_fallback)
        except Exception as e:
            log.error(f"Reasoning completion failed: {e}")
            raise LLMReasoningError(f"Reasoning failed: {e}")

    def extract_json(self, prompt: str, schema: Optional[Dict[str, Any]] = None, model: Optional[str] = None) -> Dict[str, Any]:
        log.info("LLMClient.extract_json called")
        system_prompt = "You are a data extraction agent. You must respond in ONLY valid JSON format."
        if schema:
            system_prompt += f" Ensure it matches this schema: {json.dumps(schema)}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        def _call():
            if self._using_gemini_fallback:
                content = self.gemini_client._call(model=self.gemini_default_model, messages=messages, temperature=0.1, json_mode=True)
            else:
                response = self.groq_client.chat.completions.create(
                    model=model or self.default_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = response.choices[0].message.content
            # Clean potential markdown wrapping from LLM output
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)

        try:
            return _with_retry(_call, switch_key_fn=self._switch_to_fallback)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON from LLM: {e}")
            raise LLMReasoningError("LLM did not return valid JSON.")
        except Exception as e:
            log.error(f"JSON extraction failed: {e}")
            raise LLMReasoningError(f"JSON extraction failed: {e}")

    def vision(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        log.info(f"LLMClient.vision called for image: {image_path}")

        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            raise LLMReasoningError(f"Image file not found: {image_path}")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}",
                        },
                    },
                ],
            }
        ]

        def _call():
            if self._using_gemini_fallback:
                return self.gemini_client._call(model=self.gemini_vision_model, messages=messages, temperature=0.1)
            else:
                response = self.groq_client.chat.completions.create(
                    model=model or self.vision_model,
                    messages=messages,
                    temperature=0.1,
                )
                return response.choices[0].message.content

        try:
            return _with_retry(_call, switch_key_fn=self._switch_to_fallback)
        except Exception as e:
            log.error(f"Vision completion failed: {e}")
            raise LLMReasoningError(f"Vision failed: {e}")

llm = LLMClient()
