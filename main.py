#!/usr/bin/env python3
"""
NovaAiBot - Telegram Bot for Sri Lankan A/L Students
Uses GPT-5 with fallbacks to Claude and Gemini
Limits: 1 question per user per day
"""

import os
import json
import logging
import re
import asyncio
import base64
import io
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

from telegram import Update, PhotoSize, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OWNER_USER_ID = os.getenv('OWNER_USER_ID')  # Bot owner's Telegram user ID for admin access
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
USAGE_FILE = 'user_usage.json'

# App links
NOVA_LEARN_APP_LINK = "https://play.google.com/store/apps/details?id=com.NovaScience.nova_science&ppcampaignidweb_share"
WHATSAPP_CHANNEL_LINK = "https://whatsapp.com/channel/0029Vb6hoKxBKfhyA1UJ4u2K"

# Advertisement Configuration
AD_ENABLED = os.getenv('AD_ENABLED', 'false').lower() == 'true'
AD_TYPE = os.getenv('AD_TYPE', 'text').lower()  # 'text' or 'image'
AD_TEXT = os.getenv('AD_TEXT', '📢 Download Nova Learn App for unlimited access!')
AD_IMAGE_FILE_ID = os.getenv('AD_IMAGE_FILE_ID', '')
AD_IMAGE_CAPTION = os.getenv('AD_IMAGE_CAPTION', '📢 Check out our latest offers!')


class UserUsageTracker:
    """Track user question usage per day"""

    def __init__(self, filename: str = USAGE_FILE):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load usage data from JSON file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading usage data: {e}")
        return {}

    def _save_data(self):
        """Save usage data to JSON file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")

    def can_ask_question(self, user_id: int) -> bool:
        """Check if user can ask a question today"""
        user_id_str = str(user_id)
        today = datetime.now().strftime('%Y-%m-%d')

        if user_id_str not in self.data:
            return True

        user_data = self.data[user_id_str]
        last_question_date = user_data.get('last_question_date')

        # If last question was on a different day, allow new question
        if last_question_date != today:
            return True

        # Check if they've already asked today
        questions_today = user_data.get('questions_today', 0)
        return questions_today < 1

    def record_question(self, user_id: int, username: str = None):
        """Record that user asked a question"""
        user_id_str = str(user_id)
        today = datetime.now().strftime('%Y-%m-%d')

        if user_id_str not in self.data:
            self.data[user_id_str] = {}

        user_data = self.data[user_id_str]

        # Reset count if it's a new day
        if user_data.get('last_question_date') != today:
            user_data['questions_today'] = 0

        user_data['questions_today'] = user_data.get('questions_today', 0) + 1
        user_data['last_question_date'] = today
        user_data['username'] = username
        user_data['total_questions'] = user_data.get('total_questions', 0) + 1

        self._save_data()

    def track_chat(self, chat_id: int, chat_type: str, chat_title: str = None):
        """Track chat IDs for broadcasting (users and groups)"""
        # Store chats in a separate section
        if 'chats' not in self.data:
            self.data['chats'] = {'users': {}, 'groups': {}}

        chat_id_str = str(chat_id)

        if chat_type in ['private']:
            self.data['chats']['users'][chat_id_str] = {
                'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': chat_type
            }
        elif chat_type in ['group', 'supergroup']:
            self.data['chats']['groups'][chat_id_str] = {
                'title': chat_title or 'Unknown Group',
                'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': chat_type
            }

        self._save_data()

    def get_all_user_chats(self) -> List[int]:
        """Get all user chat IDs for broadcasting"""
        if 'chats' not in self.data or 'users' not in self.data['chats']:
            return []
        return [int(chat_id) for chat_id in self.data['chats']['users'].keys()]

    def get_all_group_chats(self) -> List[int]:
        """Get all group chat IDs for broadcasting"""
        if 'chats' not in self.data or 'groups' not in self.data['chats']:
            return []
        return [int(chat_id) for chat_id in self.data['chats']['groups'].keys()]

    def get_statistics(self) -> Dict[str, Any]:
        """Get bot usage statistics"""
        total_users = len([k for k in self.data.keys() if k != 'chats'])
        total_questions = sum(user.get('total_questions', 0) for user in self.data.values() if isinstance(user, dict) and 'total_questions' in user)

        user_chats = len(self.data.get('chats', {}).get('users', {}))
        group_chats = len(self.data.get('chats', {}).get('groups', {}))

        return {
            'total_users': total_users,
            'total_questions': total_questions,
            'user_chats': user_chats,
            'group_chats': group_chats,
            'total_chats': user_chats + group_chats
        }


# Initialize usage tracker
usage_tracker = UserUsageTracker()


# ============================================================================
# LaTeX Formatting Utilities for Telegram
# ============================================================================

def convert_latex_to_telegram(text: str) -> str:
    """
    Convert LaTeX math notation to Telegram-compatible format.
    Telegram supports TeX via MarkdownV2 using \\( \\) for inline
    and \\[ \\] for display math.

    IMPORTANT: Telegram's LaTeX renderer needs proper spacing and formatting.
    - Inline math: \\( expression \\) with spaces
    - Display math: \\[ expression \\] with spaces
    """
    if not text:
        return text

    result = text

    # Convert display math: $$...$$ to \\[ ... \\] (with spaces!)
    # Telegram's LaTeX renderer needs spaces around the brackets
    result = re.sub(
        r'\$\$\s*(.*?)\s*\$\$',
        lambda m: f"\\[ {m.group(1).strip()} \\]",
        result,
        flags=re.DOTALL
    )

    # Convert inline math: $...$ to \\( ... \\) (with spaces!)
    # The spaces are critical for Telegram's renderer to work properly
    result = re.sub(
        r'\$([^\$]+?)\$',
        lambda m: f"\\( {m.group(1).strip()} \\)",
        result
    )

    return result


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    Must escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
    But NOT inside LaTeX blocks \\( ... \\) and \\[ ... \\]

    IMPORTANT: LaTeX blocks must remain unescaped for Telegram's renderer.
    """
    if not text:
        return text

    # First, protect LaTeX blocks by replacing them with placeholders
    # Use a placeholder that won't have special chars: XLATEXBLOCKX0XLATEXBLOCKX
    latex_blocks = []

    # Find and store display math blocks: \\[ ... \\] (with or without spaces)
    def store_display_math(match):
        latex_blocks.append(match.group(0))
        return f"XLATEXBLOCKX{len(latex_blocks)-1}XLATEXBLOCKX"

    text = re.sub(r'\\\[\s*.*?\s*\\\]', store_display_math, text, flags=re.DOTALL)

    # Find and store inline math blocks: \\( ... \\) (with or without spaces)
    def store_inline_math(match):
        latex_blocks.append(match.group(0))
        return f"XLATEXBLOCKX{len(latex_blocks)-1}XLATEXBLOCKX"

    text = re.sub(r'\\\(\s*.*?\s*\\\)', store_inline_math, text, flags=re.DOTALL)

    # Escape special MarkdownV2 characters in the remaining text
    special_chars = r'_*[]()~`>#+=|{}.!-'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')

    # Restore LaTeX blocks (they should not be escaped)
    for i, block in enumerate(latex_blocks):
        placeholder = f"XLATEXBLOCKX{i}XLATEXBLOCKX"
        text = text.replace(placeholder, block)

    return text


# ============================================================================
# AI System Prompts
# ============================================================================

def get_default_system_prompt() -> str:
    """Default system prompt for Nova AI Teacher"""
    return """You are NOVA AI Teacher, an expert tutor for Sri Lankan Advanced Level (A/L) Science students.
Your role is to help students with Physics, Chemistry, and Biology questions.

Guidelines:
1. Provide clear, accurate, and detailed explanations
2. Use the student's preferred language (Tamil, English, or Sinhala)
3. Break down complex concepts into easy-to-understand steps
4. Use examples relevant to the Sri Lankan A/L syllabus
5. When solving problems, show step-by-step solutions
6. Encourage critical thinking by asking guiding questions
7. Be patient, supportive, and encouraging
8. Always verify your facts and cite relevant scientific principles
9. Focus on understanding concepts rather than memorization

**SYLLABUS COMPLIANCE - CRITICAL:**
- **ONLY use derivations that are EXPLICITLY included in the Sri Lankan A/L syllabus**
- Instead of using out-of-syllabus derivations:
  * Use the formulas directly if they are given in the syllabus
  * Explain the concept without deriving it
  * State that "this derivation is beyond the A/L syllabus" if asked

**For ESSAY Questions:**
- Structure with Introduction, Body (multiple paragraphs), and Conclusion
- Use academic language and scientific terminology
- Aim for comprehensive coverage (300-800 words)

**For STRUCTURED Questions:**
- Use clear headings and subheadings
- Employ numbered lists for sequential information
- Use bullet points for features/characteristics
- Keep points concise but complete

**MATH/SCIENCE NOTATION:**
- Use LaTeX for ALL math expressions
- Inline math: $x^2 + y^2$
- Display math: $$E = mc^2$$
- Fractions: $\\frac{1}{2}$
- Greek: $\\alpha$, $\\beta$, $\\Delta$
- Units: $285.8\\,\\mathrm{kJ\\,mol^{-1}}$
- Chemistry: $H_2O$, $CO_2(g)$, $NaCl(aq)$

Remember: You are a helpful, patient, and encouraging teacher for Sri Lankan A/L students."""


# ============================================================================
# Image Processing Utilities
# ============================================================================

async def process_telegram_photo(photo: PhotoSize, context: ContextTypes.DEFAULT_TYPE) -> Tuple[str, str]:
    """
    Download and process a Telegram photo
    Returns: (base64_image, mime_type)
    """
    MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB limit

    try:
        # Get the file
        file = await context.bot.get_file(photo.file_id)

        # Check file size
        if file.file_size and file.file_size > MAX_SIZE_BYTES:
            raise ValueError(f"Image too large: {file.file_size} bytes (max {MAX_SIZE_BYTES})")

        # Download to bytes
        byte_array = await file.download_as_bytearray()

        # Convert to base64
        base64_image = base64.b64encode(bytes(byte_array)).decode('utf-8')

        # Determine MIME type (Telegram photos are usually JPEG)
        mime_type = "image/jpeg"

        logger.info(f"[IMG] Processed image: {len(base64_image)} chars, size: {file.file_size} bytes")

        return base64_image, mime_type

    except Exception as e:
        logger.error(f"[IMG] Error processing photo: {e}")
        raise


# ============================================================================
# AI API Helper Functions
# ============================================================================

async def with_timeout(coro, timeout_seconds: float, label: str):
    """Add timeout to async operation"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise Exception(f"{label}_TIMEOUT")


async def call_openai_responses_api(
    message: str,
    model: str,
    max_output_tokens: int,
    timeout_seconds: float,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """
    Call OpenAI Responses API (for GPT-5 models) with optional image
    Returns: (response_text, metadata)
    image_data: Optional tuple of (base64_image, mime_type)
    """
    import aiohttp

    # Build request body based on whether we have an image
    if image_data:
        base64_image, mime_type = image_data
        # For vision models with images, use structured input
        request_body = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{get_default_system_prompt()}\n\nUser message: {message}"
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{base64_image}"
                        }
                    ]
                }
            ],
            "reasoning": {"effort": "medium"},  # Higher effort for image analysis
            "text": {"verbosity": "medium"},
            "truncation": "disabled",
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
    else:
        # Text-only request
        request_body = {
            "model": model,
            "input": f"{get_default_system_prompt()}\n\nUser message: {message}",
            "reasoning": {"effort": "minimal"},
            "text": {"verbosity": "low"},
            "truncation": "disabled",
            "max_output_tokens": max_output_tokens,
            "store": False,
        }

    async def make_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/responses',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {OPENAI_API_KEY}',
                },
                json=request_body
            ) as response:
                return await response.json()

    result = await with_timeout(make_request(), timeout_seconds, 'OPENAI')

    # Extract text from response
    response_text = extract_text_from_openai_response(result)

    # Handle continuation if incomplete
    last_id = result.get('id')
    status = result.get('status')
    total_tokens = result.get('usage', {}).get('total_tokens', 0)

    continuation_attempts = 0
    max_continuations = 5

    while (status == 'incomplete' and last_id and continuation_attempts < max_continuations):
        continuation_attempts += 1
        logger.info(f"[AI] Continuation attempt {continuation_attempts}/{max_continuations}")

        continue_body = {
            "model": model,
            "previous_response_id": last_id,
            "max_output_tokens": 2000,
            "truncation": "disabled",
            "store": False,
        }

        async def continue_request():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.openai.com/v1/responses',
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {OPENAI_API_KEY}',
                    },
                    json=continue_body
                ) as response:
                    return await response.json()

        cont_result = await with_timeout(continue_request(), timeout_seconds, 'OPENAI')

        cont_text = extract_text_from_openai_response(cont_result)
        if cont_text:
            response_text += cont_text

        last_id = cont_result.get('id')
        status = cont_result.get('status')
        total_tokens += cont_result.get('usage', {}).get('total_tokens', 0)

    metadata = {
        'model': model,
        'tokens': total_tokens,
        'continuations': continuation_attempts
    }

    return response_text, metadata


def extract_text_from_openai_response(resp: dict) -> str:
    """Extract plain text from OpenAI Responses API structure"""
    if isinstance(resp.get('output_text'), str) and resp['output_text'].strip():
        return resp['output_text']

    if isinstance(resp.get('output'), list):
        text = ''
        for item in resp['output']:
            if item.get('type') == 'message' and isinstance(item.get('content'), list):
                for content_item in item['content']:
                    if content_item.get('type') == 'output_text':
                        text += content_item.get('text', '')
        if text.strip():
            return text

    if isinstance(resp.get('text'), str):
        return resp['text']

    return ''


async def call_claude_api(
    message: str,
    timeout_seconds: float,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """Call Anthropic Claude API with optional vision support"""
    import aiohttp

    if not CLAUDE_API_KEY:
        raise Exception("CLAUDE_API_KEY not configured")

    # Build content based on whether we have an image
    if image_data:
        base64_image, mime_type = image_data
        # Claude supports vision with base64 images
        content = [
            {
                "type": "text",
                "text": f"{get_default_system_prompt()}\n\nUser message:\n{message}"
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64_image
                }
            }
        ]
    else:
        content = f"{get_default_system_prompt()}\n\nUser message:\n{message}"

    request_body = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    async def make_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': CLAUDE_API_KEY,
                    'anthropic-version': '2023-06-01'
                },
                json=request_body
            ) as response:
                return await response.json()

    result = await with_timeout(make_request(), timeout_seconds, 'CLAUDE')

    # Extract text from Claude response
    text = ''
    if isinstance(result.get('content'), list):
        for item in result['content']:
            if item.get('type') == 'text':
                text += item.get('text', '')

    metadata = {
        'model': 'claude-3-sonnet',
        'tokens': result.get('usage', {}).get('output_tokens', 0)
    }

    return text, metadata


async def call_gemini_api(
    message: str,
    timeout_seconds: float,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """Call Google Gemini API with optional vision support"""
    import aiohttp

    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY not configured")

    # Build parts based on whether we have an image
    parts = [
        {
            "text": f"{get_default_system_prompt()}\n\nUser message:\n{message}"
        }
    ]

    if image_data:
        base64_image, mime_type = image_data
        # Gemini supports inline_data with base64
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": base64_image
            }
        })

    request_body = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000,
        }
    }

    async def make_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}',
                headers={'Content-Type': 'application/json'},
                json=request_body
            ) as response:
                return await response.json()

    result = await with_timeout(make_request(), timeout_seconds, 'GEMINI')

    # Extract text from Gemini response
    text = ''
    if isinstance(result.get('candidates'), list):
        for candidate in result['candidates']:
            if isinstance(candidate.get('content', {}).get('parts'), list):
                for part in candidate['content']['parts']:
                    text += part.get('text', '')

    metadata = {
        'model': 'gemini-1.5-flash',
        'tokens': result.get('usageMetadata', {}).get('totalTokenCount', 0)
    }

    return text, metadata


async def get_ai_response(
    message: str,
    message_length: int,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """
    Get AI response with fallback chain: GPT-5 → Claude → Gemini
    Returns: (response_text, metadata)
    image_data: Optional tuple of (base64_image, mime_type)
    """
    # Select model based on message complexity and image presence
    has_image = image_data is not None

    if has_image:
        # For images, always use the most capable model with longer timeout
        selected_model = 'gpt-5'
        max_output = 8000  # More tokens for image analysis
        timeout = 300  # 5 minutes for image processing
        logger.info("[AI] Image detected - using GPT-5 with extended settings")
    elif message_length > 200:
        selected_model = 'gpt-5'
        max_output = 4000
        timeout = 180  # 3 minutes
    elif message_length > 50:
        selected_model = 'gpt-5-mini'
        max_output = 2000
        timeout = 120  # 2 minutes
    else:
        selected_model = 'gpt-5-nano'
        max_output = 1000
        timeout = 90  # 1.5 minutes

    logger.info(f"[AI] Selected model: {selected_model}, has_image: {has_image}")

    # Try OpenAI GPT-5 first
    if OPENAI_API_KEY:
        try:
            logger.info("[AI] Attempting OpenAI GPT-5...")
            response, metadata = await call_openai_responses_api(
                message, selected_model, max_output, timeout, image_data
            )
            if response and response.strip():
                logger.info(f"[AI] ✅ OpenAI success: {len(response)} chars")
                return response, metadata
        except Exception as e:
            logger.error(f"[AI] OpenAI failed: {e}")

    # Fallback to Claude
    if CLAUDE_API_KEY:
        try:
            logger.info("[AI] Attempting Claude fallback...")
            fallback_timeout = 180 if has_image else 120
            response, metadata = await call_claude_api(message, fallback_timeout, image_data)
            if response and response.strip():
                logger.info(f"[AI] ✅ Claude success: {len(response)} chars")
                return response, metadata
        except Exception as e:
            logger.error(f"[AI] Claude failed: {e}")

    # Fallback to Gemini
    if GEMINI_API_KEY:
        try:
            logger.info("[AI] Attempting Gemini fallback...")
            fallback_timeout = 180 if has_image else 120
            response, metadata = await call_gemini_api(message, fallback_timeout, image_data)
            if response and response.strip():
                logger.info(f"[AI] ✅ Gemini success: {len(response)} chars")
                return response, metadata
        except Exception as e:
            logger.error(f"[AI] Gemini failed: {e}")

    raise Exception("All AI services failed to respond")


# ============================================================================
# Owner Verification and Admin Functions
# ============================================================================

def is_owner(user_id: int) -> bool:
    """Check if user is the bot owner"""
    if not OWNER_USER_ID:
        return False
    try:
        return str(user_id) == str(OWNER_USER_ID)
    except:
        return False


async def owner_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verify owner access and notify if unauthorized"""
    user_id = update.effective_user.id

    if is_owner(user_id):
        return True

    # Notify unauthorized access attempt
    await update.message.reply_text(
        "⛔ Unauthorized Access\n\n"
        "This command is only available to the bot owner.\n\n"
        "If you are the bot owner, please configure your OWNER_USER_ID in the .env file."
    )
    logger.warning(f"[ADMIN] Unauthorized access attempt by user {user_id} ({update.effective_user.username})")
    return False


# ============================================================================
# Advertisement Functions
# ============================================================================

async def send_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send advertisement after AI response if enabled"""
    if not AD_ENABLED:
        logger.info("[AD] Advertisements disabled")
        return

    try:
        if AD_TYPE == 'image' and AD_IMAGE_FILE_ID:
            # Send image advertisement
            logger.info(f"[AD] Sending image advertisement to chat {update.effective_chat.id}")
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=AD_IMAGE_FILE_ID,
                caption=AD_IMAGE_CAPTION,
                parse_mode=ParseMode.MARKDOWN
            )
        elif AD_TYPE == 'text' and AD_TEXT:
            # Send text advertisement
            logger.info(f"[AD] Sending text advertisement to chat {update.effective_chat.id}")
            await update.message.reply_text(
                AD_TEXT,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            logger.warning("[AD] Advertisement enabled but no valid ad content configured")
    except Exception as e:
        logger.error(f"[AD] Failed to send advertisement: {e}")


# ============================================================================
# Command Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    # Track this chat for broadcasting
    chat = update.effective_chat
    usage_tracker.track_chat(chat.id, chat.type, chat.title)

    # Log user ID for owner configuration
    user_id = update.effective_user.id
    logger.info(f"[BOT] /start from user {user_id} ({update.effective_user.username}) in chat {chat.id} ({chat.type})")

    welcome_message = (
        "🤖 Welcome to NovaAiBot!\n\n"
        "I'm here to answer your questions using advanced AI technology.\n\n"
        "📝 How to use:\n"
        "• Send me text questions directly\n"
        "• Send photos of problems, diagrams, or equations\n"
        "• Add a caption to photos for specific questions\n"
        "• Each user gets 1 FREE question per day\n\n"
        "🎯 Perfect for:\n"
        "• Physics problems with diagrams\n"
        "• Chemistry equations and structures\n"
        "• Biology diagrams and illustrations\n"
        "• Math equations from textbooks\n\n"
        "💡 Want unlimited access?\n"
        f"Download Nova Learn App: {NOVA_LEARN_APP_LINK}\n\n"
        f"📢 Join our WhatsApp channel: {WHATSAPP_CHANNEL_LINK}\n\n"
        "Send me a question or photo to get started!"
    )
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_message = (
        "🆘 NovaAiBot Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/status - Check your daily question limit\n\n"
        "How to Ask Questions:\n\n"
        "📝 Text Questions:\n"
        "Just type and send your question\n\n"
        "📸 Image Questions:\n"
        "1. Take a photo of your problem/diagram\n"
        "2. Add a caption (optional but recommended)\n"
        "3. Send it to the bot\n\n"
        "Examples:\n"
        "• Photo of physics problem + caption: \"Solve this\"\n"
        "• Photo of chemical structure + caption: \"What compound is this?\"\n"
        "• Photo of biology diagram + caption: \"Explain this process\"\n"
        "• Photo without caption: Bot will analyze and explain\n\n"
        "Limits:\n"
        "• 1 free question per day (text or image)\n"
        "• Images must be under 5MB\n"
        "• Images should be clear and readable\n\n"
        f"📱 For unlimited questions, download: {NOVA_LEARN_APP_LINK}\n"
        f"📢 Join our WhatsApp: {WHATSAPP_CHANNEL_LINK}"
    )
    await update.message.reply_text(help_message)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    user_id = update.effective_user.id
    can_ask = usage_tracker.can_ask_question(user_id)

    if can_ask:
        status_message = (
            "✅ You have 1 question remaining today!\n\n"
            "Send me your question and I'll answer it using AI."
        )
    else:
        status_message = (
            "⏰ You've used your daily question limit!\n\n"
            "Come back tomorrow for another free question, or:\n\n"
            f"📱 Download Nova Learn App for unlimited access:\n{NOVA_LEARN_APP_LINK}\n\n"
            f"📢 Join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}"
        )

    await update.message.reply_text(status_message)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command (Owner only)"""
    if not await owner_only(update, context):
        return

    # Get statistics
    stats = usage_tracker.get_statistics()

    # Create inline keyboard with settings options
    keyboard = [
        [InlineKeyboardButton("📊 View Statistics", callback_data="settings_stats")],
        [InlineKeyboardButton("📢 Broadcast to Users", callback_data="settings_broadcast_users")],
        [InlineKeyboardButton("📢 Broadcast to Groups", callback_data="settings_broadcast_groups")],
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="settings_broadcast_all")],
        [InlineKeyboardButton("❌ Close", callback_data="settings_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_message = (
        "⚙️ **Bot Settings** (Owner Only)\n\n"
        f"👥 Total Users: {stats['total_users']}\n"
        f"❓ Total Questions: {stats['total_questions']}\n"
        f"💬 User Chats: {stats['user_chats']}\n"
        f"👥 Group Chats: {stats['group_chats']}\n\n"
        "Choose an option below:"
    )

    await update.message.reply_text(settings_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not is_owner(user_id):
        await query.edit_message_text("⛔ Unauthorized access. This feature is only for the bot owner.")
        return

    data = query.data

    if data == "settings_stats":
        # Show detailed statistics
        stats = usage_tracker.get_statistics()
        stats_message = (
            "📊 **Detailed Statistics**\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"❓ Total Questions Asked: {stats['total_questions']}\n"
            f"💬 Active User Chats: {stats['user_chats']}\n"
            f"👥 Active Group Chats: {stats['group_chats']}\n"
            f"📱 Total Chats: {stats['total_chats']}\n\n"
            "Use /settings to return to main menu."
        )
        await query.edit_message_text(stats_message, parse_mode=ParseMode.MARKDOWN)

    elif data == "settings_broadcast_users":
        await query.edit_message_text(
            "📢 **Broadcast to Users**\n\n"
            "**Text Broadcast:**\n"
            "`/broadcast users <your message>`\n\n"
            "**Image Broadcast:**\n"
            "Send photo with caption: `#broadcast users <message>`\n\n"
            "Example:\n"
            "`/broadcast users Hello! Check out our new feature!`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "settings_broadcast_groups":
        await query.edit_message_text(
            "📢 **Broadcast to Groups**\n\n"
            "**Text Broadcast:**\n"
            "`/broadcast groups <your message>`\n\n"
            "**Image Broadcast:**\n"
            "Send photo with caption: `#broadcast groups <message>`\n\n"
            "Example:\n"
            "`/broadcast groups Important update for all groups!`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "settings_broadcast_all":
        await query.edit_message_text(
            "📢 **Broadcast to All**\n\n"
            "**Text Broadcast:**\n"
            "`/broadcast all <your message>`\n\n"
            "**Image Broadcast:**\n"
            "Send photo with caption: `#broadcast all <message>`\n\n"
            "Examples:\n"
            "• Text: `/broadcast all New feature available now!`\n"
            "• Image: Send photo with caption `#broadcast all Check this out!`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "settings_close":
        await query.edit_message_text("⚙️ Settings closed.")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command (Owner only) - Send messages to all users/groups"""
    if not await owner_only(update, context):
        return

    # Parse command: /broadcast <target> <message>
    # target can be: users, groups, or all
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "Usage:\n"
            "`/broadcast users <message>` - Send to all users\n"
            "`/broadcast groups <message>` - Send to all groups\n"
            "`/broadcast all <message>` - Send to everyone\n\n"
            "Example:\n"
            "`/broadcast all Check out our new features!`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    target = context.args[0].lower()
    message = ' '.join(context.args[1:])

    if target not in ['users', 'groups', 'all']:
        await update.message.reply_text(
            "❌ Invalid target. Use: `users`, `groups`, or `all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Get chat IDs based on target
    if target == 'users':
        chat_ids = usage_tracker.get_all_user_chats()
        target_name = "users"
    elif target == 'groups':
        chat_ids = usage_tracker.get_all_group_chats()
        target_name = "groups"
    else:  # all
        chat_ids = usage_tracker.get_all_user_chats() + usage_tracker.get_all_group_chats()
        target_name = "all users and groups"

    if not chat_ids:
        await update.message.reply_text(f"⚠️ No {target_name} found to broadcast to.")
        return

    # Confirm broadcast
    await update.message.reply_text(
        f"📢 **Broadcasting to {len(chat_ids)} {target_name}...**\n\n"
        f"Message: {message}\n\n"
        "Please wait..."
    )

    # Send broadcast
    success_count = 0
    fail_count = 0

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📢 **Announcement from NovaAI**\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Small delay to avoid rate limiting
        except Exception as e:
            logger.error(f"[BROADCAST] Failed to send to {chat_id}: {e}")
            fail_count += 1

    # Report results
    result_message = (
        f"✅ **Broadcast Complete**\n\n"
        f"📊 Results:\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📱 Total: {len(chat_ids)}"
    )
    await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"[BROADCAST] Completed: {success_count} sent, {fail_count} failed to {target_name}")


async def broadcast_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image broadcasts from owner (photo with #broadcast caption)"""
    user_id = update.effective_user.id

    logger.info(f"[BROADCAST_IMG] Handler triggered by user {user_id}")

    # Only owner can broadcast
    if not is_owner(user_id):
        logger.warning(f"[BROADCAST_IMG] Non-owner user {user_id} tried to broadcast")
        return  # Silently ignore non-owner photo messages with #broadcast

    caption = update.message.caption or ""
    logger.info(f"[BROADCAST_IMG] Caption: {caption}")

    # Check if caption starts with #broadcast
    if not caption.startswith("#broadcast "):
        logger.info(f"[BROADCAST_IMG] Caption doesn't start with #broadcast, skipping")
        return  # Not a broadcast image

    # Parse the caption: #broadcast <target> <message>
    parts = caption.split(None, 2)  # Split into max 3 parts
    logger.info(f"[BROADCAST_IMG] Parsed parts: {parts}")

    if len(parts) < 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "To broadcast an image, send a photo with caption:\n"
            "`#broadcast users <message>`\n"
            "`#broadcast groups <message>`\n"
            "`#broadcast all <message>`\n\n"
            "Example:\n"
            "Send photo with caption: `#broadcast all Check out this new feature!`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    target = parts[1].lower()
    message = parts[2] if len(parts) > 2 else ""

    if target not in ['users', 'groups', 'all']:
        await update.message.reply_text(
            "❌ Invalid target. Use: `users`, `groups`, or `all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Get chat IDs based on target
    if target == 'users':
        chat_ids = usage_tracker.get_all_user_chats()
        target_name = "users"
    elif target == 'groups':
        chat_ids = usage_tracker.get_all_group_chats()
        target_name = "groups"
    else:  # all
        chat_ids = usage_tracker.get_all_user_chats() + usage_tracker.get_all_group_chats()
        target_name = "all users and groups"

    if not chat_ids:
        await update.message.reply_text(f"⚠️ No {target_name} found to broadcast to.")
        return

    # Get the photo
    photo = update.message.photo[-1]  # Get largest photo

    # Confirm broadcast
    await update.message.reply_text(
        f"📢 **Broadcasting image to {len(chat_ids)} {target_name}...**\n\n"
        f"Caption: {message if message else '(no caption)'}\n\n"
        "Please wait..."
    )

    # Send broadcast
    success_count = 0
    fail_count = 0

    # Prepare caption with announcement header
    full_caption = f"📢 **Announcement from NovaAI**\n\n{message}" if message else "📢 **Announcement from NovaAI**"

    for chat_id in chat_ids:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo.file_id,
                caption=full_caption,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Small delay to avoid rate limiting
        except Exception as e:
            logger.error(f"[BROADCAST_IMG] Failed to send to {chat_id}: {e}")
            fail_count += 1

    # Report results
    result_message = (
        f"✅ **Image Broadcast Complete**\n\n"
        f"📊 Results:\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📱 Total: {len(chat_ids)}"
    )
    await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"[BROADCAST_IMG] Completed: {success_count} sent, {fail_count} failed to {target_name}")


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user questions (text only) with AI response"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    question = update.message.text

    # Track this chat for broadcasting
    chat = update.effective_chat
    usage_tracker.track_chat(chat.id, chat.type, chat.title)

    # Check if user can ask a question (Owner bypass - owner can ask unlimited questions)
    if not usage_tracker.can_ask_question(user_id) and not is_owner(user_id):
        limit_message = (
            "⚠️ Daily Limit Reached!\n\n"
            "You've already asked your free question today.\n\n"
            "🚀 Want unlimited access to NovaAI?\n\n"
            f"📱 Download Nova Learn App:\n{NOVA_LEARN_APP_LINK}\n\n"
            "Get:\n"
            "✨ Unlimited AI-powered answers\n"
            "✨ Advanced learning features\n"
            "✨ Personalized study plans\n"
            "✨ And much more!\n\n"
            f"📢 For more info, join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}\n\n"
            "💡 Your free question resets tomorrow!"
        )
        await update.message.reply_text(limit_message)
        return

    # Send "typing" action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Send "please wait" message
    wait_message = await update.message.reply_text(
        "⏳ Processing your question...\n\n"
        "🤖 AI is analyzing and preparing a detailed answer.\n"
        "⏱️ This may take 30-90 seconds.\n\n"
        "Please wait..."
    )

    try:
        logger.info(f"[BOT] Text question from user {user_id}: {question[:100]}...")

        # Get AI response with fallback chain (no image)
        message_length = len(question)
        ai_response, metadata = await get_ai_response(question, message_length, None)

        if not ai_response or not ai_response.strip():
            raise Exception("Received empty response from AI")

        logger.info(f"[BOT] Got response: {len(ai_response)} chars, model: {metadata.get('model')}")

        # Record the question
        usage_tracker.record_question(user_id, username)

        # Convert LaTeX to Telegram format
        formatted_response = convert_latex_to_telegram(ai_response)

        # Add footer
        footer = (
            "\n\n━━━━━━━━━━━━━━━━━━\n"
            "🤖 Powered by NovaAI\n"
            f"📱 Get unlimited access: {NOVA_LEARN_APP_LINK}\n"
            "⚠️ You've used your daily free question. Come back tomorrow!"
        )

        full_response = formatted_response + footer

        # Escape for MarkdownV2 (protects LaTeX blocks)
        escaped_response = escape_markdown_v2(full_response)

        # Split long messages (Telegram limit: 4096 chars)
        MAX_MESSAGE_LENGTH = 4000  # Leave buffer for escaping

        if len(escaped_response) <= MAX_MESSAGE_LENGTH:
            # Send as single message with MarkdownV2
            try:
                await update.message.reply_text(
                    escaped_response,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception as parse_error:
                # Fallback to plain text if MarkdownV2 fails
                logger.warning(f"[BOT] MarkdownV2 parse failed, sending as plain text: {parse_error}")
                await update.message.reply_text(full_response)
        else:
            # Split into multiple messages
            parts = []
            current_part = ""

            for line in full_response.split('\n'):
                if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += ("\n" if current_part else "") + line

            if current_part:
                parts.append(current_part)

            # Send parts
            for i, part in enumerate(parts):
                # Only add footer to last part
                if i == len(parts) - 1:
                    part_with_footer = part + footer
                else:
                    part_with_footer = part

                part_latex = convert_latex_to_telegram(part_with_footer)
                part_escaped = escape_markdown_v2(part_latex)

                try:
                    await update.message.reply_text(
                        part_escaped,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                except Exception:
                    # Fallback to plain text
                    await update.message.reply_text(part_with_footer)

                # Small delay between messages
                if i < len(parts) - 1:
                    await asyncio.sleep(0.5)

        logger.info(f"[BOT] ✅ Response sent successfully to user {user_id}")

        # Send advertisement after successful response
        await send_advertisement(update, context)

    except Exception as e:
        logger.error(f"[BOT] Error processing question: {e}", exc_info=True)
        error_message = (
            "❌ Sorry, I encountered an error processing your question.\n\n"
            "This could be due to:\n"
            "• High server load\n"
            "• Complex question requiring more processing\n"
            "• Temporary API issues\n\n"
            "Please try:\n"
            "• Simplifying your question\n"
            "• Trying again in a few moments\n\n"
            f"📱 For unlimited access and priority support:\n{NOVA_LEARN_APP_LINK}\n\n"
            f"📢 Join our WhatsApp channel: {WHATSAPP_CHANNEL_LINK}"
        )
        await update.message.reply_text(error_message)


async def handle_photo_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle questions with images"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # Track this chat for broadcasting
    chat = update.effective_chat
    usage_tracker.track_chat(chat.id, chat.type, chat.title)

    # Get caption as the question, or use default
    question = update.message.caption or "Please analyze this image and explain what you see. If it's a problem, solve it. If it's a diagram, explain it."

    # If caption starts with #broadcast, it should be handled by broadcast handler
    # This is a safety check in case the handler didn't catch it
    if question.startswith("#broadcast"):
        if is_owner(user_id):
            await update.message.reply_text(
                "⚠️ **Broadcast Format Error**\n\n"
                "Make sure your caption starts with:\n"
                "`#broadcast all <message>`\n"
                "`#broadcast users <message>`\n"
                "`#broadcast groups <message>`\n\n"
                "Note: There must be exactly one space after 'broadcast'",
                parse_mode=ParseMode.MARKDOWN
            )
        return  # Don't process as a question

    # Check if user can ask a question (Owner bypass - owner can ask unlimited questions)
    if not usage_tracker.can_ask_question(user_id) and not is_owner(user_id):
        limit_message = (
            "⚠️ Daily Limit Reached!\n\n"
            "You've already asked your free question today.\n\n"
            "🚀 Want unlimited access to NovaAI?\n\n"
            f"📱 Download Nova Learn App:\n{NOVA_LEARN_APP_LINK}\n\n"
            "Get:\n"
            "✨ Unlimited AI-powered answers\n"
            "✨ Advanced learning features\n"
            "✨ Personalized study plans\n"
            "✨ And much more!\n\n"
            f"📢 For more info, join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}\n\n"
            "💡 Your free question resets tomorrow!"
        )
        await update.message.reply_text(limit_message)
        return

    # Send "typing" action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Send "please wait" message for image analysis
    wait_message = await update.message.reply_text(
        "⏳ Processing your image...\n\n"
        "🤖 AI is analyzing the image and preparing a detailed answer.\n"
        "⏱️ Image analysis may take 2-5 minutes.\n\n"
        "Please wait..."
    )

    try:
        logger.info(f"[BOT] Photo question from user {user_id}: {question[:100]}...")

        # Get the largest photo (best quality)
        photo = update.message.photo[-1]

        # Process the image
        try:
            base64_image, mime_type = await process_telegram_photo(photo, context)
            image_data = (base64_image, mime_type)
            logger.info(f"[BOT] Image processed successfully")
        except ValueError as ve:
            # Image too large
            error_message = (
                "❌ Image Too Large!\n\n"
                f"{str(ve)}\n\n"
                "Please:\n"
                "• Crop the image to focus on the important part\n"
                "• Compress the image\n"
                "• Try a lower resolution\n\n"
                "Maximum size: 5MB"
            )
            await update.message.reply_text(error_message)
            return
        except Exception as e:
            logger.error(f"[BOT] Image processing failed: {e}")
            error_message = (
                "❌ Failed to process image\n\n"
                "Please try:\n"
                "• Sending a different image format\n"
                "• Compressing the image\n"
                "• Trying again in a moment\n\n"
                f"Error: {str(e)}"
            )
            await update.message.reply_text(error_message)
            return

        # Get AI response with image
        message_length = len(question)
        ai_response, metadata = await get_ai_response(question, message_length, image_data)

        if not ai_response or not ai_response.strip():
            raise Exception("Received empty response from AI")

        logger.info(f"[BOT] Got response: {len(ai_response)} chars, model: {metadata.get('model')}")

        # Record the question
        usage_tracker.record_question(user_id, username)

        # Convert LaTeX to Telegram format
        formatted_response = convert_latex_to_telegram(ai_response)

        # Add footer
        footer = (
            "\n\n━━━━━━━━━━━━━━━━━━\n"
            "🤖 Powered by NovaAI\n"
            "📸 Image analysis complete\n"
            f"📱 Get unlimited access: {NOVA_LEARN_APP_LINK}\n"
            "⚠️ You've used your daily free question. Come back tomorrow!"
        )

        full_response = formatted_response + footer

        # Escape for MarkdownV2 (protects LaTeX blocks)
        escaped_response = escape_markdown_v2(full_response)

        # Split long messages (Telegram limit: 4096 chars)
        MAX_MESSAGE_LENGTH = 4000  # Leave buffer for escaping

        if len(escaped_response) <= MAX_MESSAGE_LENGTH:
            # Send as single message with MarkdownV2
            try:
                await update.message.reply_text(
                    escaped_response,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception as parse_error:
                # Fallback to plain text if MarkdownV2 fails
                logger.warning(f"[BOT] MarkdownV2 parse failed, sending as plain text: {parse_error}")
                await update.message.reply_text(full_response)
        else:
            # Split into multiple messages
            parts = []
            current_part = ""

            for line in full_response.split('\n'):
                if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += ("\n" if current_part else "") + line

            if current_part:
                parts.append(current_part)

            # Send parts
            for i, part in enumerate(parts):
                # Only add footer to last part
                if i == len(parts) - 1:
                    part_with_footer = part + footer
                else:
                    part_with_footer = part

                part_latex = convert_latex_to_telegram(part_with_footer)
                part_escaped = escape_markdown_v2(part_latex)

                try:
                    await update.message.reply_text(
                        part_escaped,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                except Exception:
                    # Fallback to plain text
                    await update.message.reply_text(part_with_footer)

                # Small delay between messages
                if i < len(parts) - 1:
                    await asyncio.sleep(0.5)

        logger.info(f"[BOT] ✅ Response sent successfully to user {user_id}")

        # Send advertisement after successful response
        await send_advertisement(update, context)

    except Exception as e:
        logger.error(f"[BOT] Error processing photo question: {e}", exc_info=True)
        error_message = (
            "❌ Sorry, I encountered an error processing your image.\n\n"
            "This could be due to:\n"
            "• Image format not supported\n"
            "• High server load\n"
            "• Complex image requiring more processing\n"
            "• Temporary API issues\n\n"
            "Please try:\n"
            "• Using a clearer image\n"
            "• Adding a text caption describing what you need help with\n"
            "• Trying again in a few moments\n\n"
            f"📱 For unlimited access and priority support:\n{NOVA_LEARN_APP_LINK}\n\n"
            f"📢 Join our WhatsApp channel: {WHATSAPP_CHANNEL_LINK}"
        )
        await update.message.reply_text(error_message)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not found in environment variables!")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))

    # Owner-only commands
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    # Callback query handler for inline keyboard buttons
    application.add_handler(CallbackQueryHandler(settings_callback_handler))

    # Handle broadcast images from owner (checked first before regular photo questions)
    application.add_handler(
        MessageHandler(
            filters.PHOTO & filters.CAPTION & filters.Regex(r'^#broadcast\s'),
            broadcast_image_handler
        )
    )

    # Handle photo messages (questions with images)
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo_question
        )
    )

    # Handle all text messages (questions without images)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_question
        )
    )

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("NovaAiBot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
