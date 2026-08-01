import os
import logging
from llm_client import call_model

def _resolve_path(path: str) -> str:
    """Helper to find the file path relative to current working directory."""
    for prefix in ["", "../", "../dataset/", "dataset/", "../../dataset/"]:
        p = os.path.join(prefix, path)
        if os.path.exists(p):
            return p
    return path

def get_media_content(bundle: dict) -> str | None:
    """
    If bundle['message']['media_type'] is 'image': load the file, send to Gemini,
    asking for a factual description and suspicious indicators. Return the caption.
    
    If bundle['message']['media_type'] is 'voice': load the file, send to Gemini,
    asking for a plain transcript plus a one-line note on tone/urgency. Return the transcript.
    
    On failure, log a warning and return '[media processing failed]'.
    """
    msg = bundle.get('message', {})
    media_type = msg.get('media_type')
    
    if media_type not in ('image', 'voice'):
        return None
        
    try:
        media_data = None
        mime_type = None
        prompt = ""
        
        if media_type == 'image':
            img_info = bundle.get('image')
            if not img_info:
                return None
            path = _resolve_path(img_info.get('file_path'))
            if not path or not os.path.exists(path):
                logging.warning(f"Image file not found: {img_info.get('file_path')}")
                return "[media processing failed]"
                
            mime_type = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            with open(path, "rb") as f:
                media_data = f.read()
                
            prompt = "Describe this image factually in 1-2 sentences, noting any text, urgency signals, payment requests, or suspicious/scam indicators visible."
            
        elif media_type == 'voice':
            voice_info = bundle.get('voice_note')
            if not voice_info:
                return None
            path = _resolve_path(voice_info.get('file_path'))
            if not path or not os.path.exists(path):
                logging.warning(f"Voice file not found: {voice_info.get('file_path')}")
                return "[media processing failed]"
                
            mime_type = "audio/mpeg" if path.lower().endswith((".mp3", ".mpeg")) else "audio/ogg"
            with open(path, "rb") as f:
                media_data = f.read()
                
            prompt = "Please provide a plain transcript of this audio, plus a one-line note on tone/urgency if audibly present."
            
        if media_data and mime_type:
            response = call_model(prompt=prompt, media_data=media_data, mime_type=mime_type)
            return response.get("text", "").strip()
            
    except Exception as e:
        logging.warning(f"Failed to process media for message {msg.get('message_id')}: {e}")
        return "[media processing failed]"
        
    return None
